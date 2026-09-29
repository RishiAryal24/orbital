"""
PyLoom Technologies — Zero-YAML Manifest Synthesizer.

Converts simple application configuration (git repo, port, env vars, domain)
into complete, production-grade Argo Rollouts, Services, Secrets, and Ingress manifests.
Developers never have to write raw Kubernetes YAML.
"""

from typing import Any, Dict, List, Optional
import yaml


class ManifestSynthesizer:
    """Dynamically synthesizes production Kubernetes & Argo Rollouts manifests."""

    @staticmethod
    def generate_rollout_manifest(
        app_name: str,
        namespace: str,
        image: str,
        target_port: int = 8000,
        replicas: int = 2,
        cpu_request: str = "100m",
        cpu_limit: str = "500m",
        memory_request: str = "128Mi",
        memory_limit: str = "512Mi",
        env_vars: Optional[Dict[str, str]] = None,
        secret_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate Argo Rollouts Blue/Green deployment manifest."""
        env_list: List[Dict[str, Any]] = []
        if env_vars:
            for key, val in env_vars.items():
                env_list.append({"name": key, "value": str(val)})

        containers_spec: List[Dict[str, Any]] = [
            {
                "name": app_name,
                "image": image,
                "ports": [{"containerPort": target_port, "name": "http"}],
                "resources": {
                    "requests": {"cpu": cpu_request, "memory": memory_request},
                    "limits": {"cpu": cpu_limit, "memory": memory_limit},
                },
                "securityContext": {
                    "allowPrivilegeEscalation": False,
                    "readOnlyRootFilesystem": True,
                    "capabilities": {"drop": ["ALL"]},
                },
                "volumeMounts": [{"name": "tmp-dir", "mountPath": "/tmp"}],
            }
        ]

        if env_list:
            containers_spec[0]["env"] = env_list

        if secret_name:
            containers_spec[0]["envFrom"] = [{"secretRef": {"name": secret_name}}]

        return {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Rollout",
            "metadata": {
                "name": app_name,
                "namespace": namespace,
                "labels": {"app": app_name},
            },
            "spec": {
                "replicas": replicas,
                "revisionHistoryLimit": 5,
                "selector": {"matchLabels": {"app": app_name}},
                "strategy": {
                    "blueGreen": {
                        "activeService": f"{app_name}-active",
                        "previewService": f"{app_name}-preview",
                        "autoPromotionEnabled": True,
                        "autoPromotionSeconds": 30,
                    }
                },
                "template": {
                    "metadata": {"labels": {"app": app_name}},
                    "spec": {
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 1000,
                            "runAsGroup": 1000,
                            "fsGroup": 1000,
                        },
                        "containers": containers_spec,
                        "volumes": [{"name": "tmp-dir", "emptyDir": {}}],
                    },
                },
            },
        }

    @staticmethod
    def generate_services(
        app_name: str, namespace: str, target_port: int = 8000
    ) -> List[Dict[str, Any]]:
        """Generate co-existing Active and Preview Kubernetes Services for Blue/Green."""
        services = []
        for role in ["active", "preview"]:
            services.append(
                {
                    "apiVersion": "v1",
                    "kind": "Service",
                    "metadata": {
                        "name": f"{app_name}-{role}",
                        "namespace": namespace,
                        "labels": {"app": app_name, "role": role},
                    },
                    "spec": {
                        "type": "ClusterIP",
                        "ports": [
                            {
                                "port": 80,
                                "targetPort": target_port,
                                "protocol": "TCP",
                                "name": "http",
                            }
                        ],
                        "selector": {"app": app_name},
                    },
                }
            )
        return services

    @staticmethod
    def generate_ingress(
        app_name: str, namespace: str, domain: str
    ) -> Dict[str, Any]:
        """Generate Ingress manifest routing public domain to the active service."""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": f"{app_name}-ingress",
                "namespace": namespace,
                "annotations": {
                    "kubernetes.io/ingress.class": "traefik",
                    "traefik.ingress.kubernetes.io/router.entrypoints": "web,websecure",
                },
            },
            "spec": {
                "rules": [
                    {
                        "host": domain,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": f"{app_name}-active",
                                            "port": {"number": 80},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
        }

    @classmethod
    def synthesize_all_yaml(
        cls,
        app_name: str,
        namespace: str,
        image: str,
        domain: Optional[str] = None,
        target_port: int = 8000,
        replicas: int = 2,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """Synthesize all manifests into a single, multi-document YAML stream."""
        docs = []
        # 1. Rollout
        docs.append(
            cls.generate_rollout_manifest(
                app_name=app_name,
                namespace=namespace,
                image=image,
                target_port=target_port,
                replicas=replicas,
                env_vars=env_vars,
            )
        )
        # 2. Active & Preview Services
        docs.extend(cls.generate_services(app_name, namespace, target_port))
        # 3. Ingress (if domain provided)
        if domain:
            docs.append(cls.generate_ingress(app_name, namespace, domain))

        return "---\n".join(yaml.dump(doc, sort_keys=False) for doc in docs)

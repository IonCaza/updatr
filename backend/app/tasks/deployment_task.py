from __future__ import annotations

import logging

from app.database import SyncSession
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="build_worker_image", bind=True, max_retries=0)
def build_worker_image(self, build_id: str):
    from app.services.build_service import build_and_push

    logger.info("Starting build %s", build_id)
    with SyncSession() as db:
        build_and_push(build_id, db)
    logger.info("Build %s finished", build_id)


@celery_app.task(name="deploy_worker_to_host", bind=True, max_retries=0)
def deploy_worker_to_host(self, deployment_id: str):
    from app.services.deploy_service import deploy_worker

    logger.info("Starting deployment %s", deployment_id)
    with SyncSession() as db:
        deploy_worker(deployment_id, db)
    logger.info("Deployment %s finished", deployment_id)


@celery_app.task(name="stop_deployed_worker", bind=True, max_retries=0)
def stop_deployed_worker(self, deployment_id: str):
    from app.services.deploy_service import stop_worker
    from app.models.deployment import WorkerDeployment

    logger.info("Stopping deployment %s", deployment_id)
    with SyncSession() as db:
        deployment = db.query(WorkerDeployment).filter(WorkerDeployment.id == deployment_id).first()
        if deployment:
            stop_worker(deployment, db)
    logger.info("Deployment %s stopped", deployment_id)


@celery_app.task(name="restart_deployed_worker", bind=True, max_retries=0)
def restart_deployed_worker(self, deployment_id: str):
    from app.services.deploy_service import restart_worker
    from app.models.deployment import WorkerDeployment

    logger.info("Restarting deployment %s", deployment_id)
    with SyncSession() as db:
        deployment = db.query(WorkerDeployment).filter(WorkerDeployment.id == deployment_id).first()
        if deployment:
            restart_worker(deployment, db)
    logger.info("Deployment %s restarted", deployment_id)


@celery_app.task(name="remove_deployed_worker", bind=True, max_retries=0)
def remove_deployed_worker(self, deployment_id: str):
    from app.services.deploy_service import remove_worker
    from app.models.deployment import WorkerDeployment

    logger.info("Removing deployment %s", deployment_id)
    with SyncSession() as db:
        deployment = db.query(WorkerDeployment).filter(WorkerDeployment.id == deployment_id).first()
        if deployment:
            remove_worker(deployment, db)
    logger.info("Deployment %s removed", deployment_id)


@celery_app.task(name="check_deployment_health")
def check_deployment_health():
    from app.services.deploy_service import check_all_deployments_health

    with SyncSession() as db:
        check_all_deployments_health(db)

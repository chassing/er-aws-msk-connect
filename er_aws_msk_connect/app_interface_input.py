from __future__ import annotations

from typing import Literal, Self

from external_resources_io.input import AppInterfaceProvision
from pydantic import BaseModel, model_validator


class CustomPlugin(BaseModel):
    """aws_mskconnect_custom_plugin - plugin location in S3."""

    s3_bucket_arn: str
    s3_key: str
    s3_object_version: str | None = None
    content_type: Literal["zip", "jar"]


class ScaleInPolicy(BaseModel):
    """aws_mskconnect_connector.capacity.autoscaling.scale_in_policy"""

    cpu_utilization_percentage: int = 20


class ScaleOutPolicy(BaseModel):
    """aws_mskconnect_connector.capacity.autoscaling.scale_out_policy"""

    cpu_utilization_percentage: int = 80


class AutoscalingCapacity(BaseModel):
    """aws_mskconnect_connector.capacity.autoscaling"""

    min_worker_count: int
    max_worker_count: int
    mcu_count: Literal[1, 2, 4, 8] = 1
    scale_in_policy: ScaleInPolicy = ScaleInPolicy()
    scale_out_policy: ScaleOutPolicy = ScaleOutPolicy()


class ProvisionedCapacity(BaseModel):
    """aws_mskconnect_connector.capacity.provisioned_capacity"""

    worker_count: int = 1
    mcu_count: Literal[1, 2, 4, 8] = 1


class Capacity(BaseModel):
    """aws_mskconnect_connector.capacity - default: provisioned 1 MCU 1 worker."""

    autoscaling: AutoscalingCapacity | None = None
    provisioned_capacity: ProvisionedCapacity | None = None

    @model_validator(mode="after")
    def exactly_one_capacity_type(self) -> Self:
        """If neither is set, default to provisioned. If both are set, error."""
        if self.autoscaling and self.provisioned_capacity:
            msg = "Only one of 'autoscaling' or 'provisioned_capacity' can be set"
            raise ValueError(msg)
        if not self.autoscaling and not self.provisioned_capacity:
            self.provisioned_capacity = ProvisionedCapacity()
        return self


class CloudwatchLogsLogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery.worker_log_delivery.cloudwatch_logs"""

    enabled: bool
    retention_in_days: Literal[
        1,
        3,
        5,
        7,
        14,
        30,
        60,
        90,
        120,
        150,
        180,
        365,
        400,
        545,
        731,
        1096,
        1827,
        2192,
        2557,
        2922,
        3288,
        3653,
    ]


class S3LogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery.worker_log_delivery.s3"""

    enabled: bool
    bucket: str
    prefix: str | None = None


class LogDelivery(BaseModel):
    """aws_mskconnect_connector.log_delivery"""

    cloudwatch_logs: CloudwatchLogsLogDelivery | None = None
    s3: S3LogDelivery | None = None


class VpcConfig(BaseModel):
    """aws_mskconnect_connector.kafka_cluster.apache_kafka_cluster.vpc"""

    subnets: list[str]
    security_groups: list[str]


class MskConnectData(BaseModel):
    """Data model for AWS MSK Connect.

    Fields populated by qontract-reconcile (resolved from references):
    - kafka_cluster_bootstrap_servers: from MSK cluster vault output secret
    - vpc: subnets + security_groups from MSK cluster defaults
    - service_execution_role: IAM role identifier, resolved to ARN via Terraform data source

    Fields with defaults in this module:
    - kafka_connect_version: "3.7.1"
    - capacity: provisioned, 1 MCU, 1 worker
    """

    # app-interface metadata
    identifier: str
    region: str
    tags: dict[str, str] = {}

    # resolved by qontract-reconcile from msk_cluster reference
    msk_cluster: str
    kafka_cluster_bootstrap_servers: str
    vpc: VpcConfig

    # resolved by qontract-reconcile from service_execution_role reference
    service_execution_role: str

    # connector config (from tenant defaults file)
    connector_configuration: dict[str, str]
    kafka_connect_version: Literal["2.7.1", "3.7.x"] = "3.7.x"

    # custom plugin (from tenant defaults file, s3_bucket_arn built by reconcile)
    custom_plugin: CustomPlugin

    # optional (defaults in this module)
    capacity: Capacity = Capacity()
    worker_configuration: str | None = None
    log_delivery: LogDelivery | None = None


class AppInterfaceInput(BaseModel):
    """Input model for AWS MSK Connect."""

    data: MskConnectData
    provision: AppInterfaceProvision

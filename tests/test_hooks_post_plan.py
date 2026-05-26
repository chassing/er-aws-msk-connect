from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from external_resources_io.terraform import Action, ResourceChange

from hooks.post_plan import MskConnectPlanValidator, TerraformJsonPlanParser

if TYPE_CHECKING:
    from collections.abc import Iterator

    from er_aws_msk_connect.app_interface_input import AppInterfaceInput

MOCK_ROLE_ARN = "arn:aws:iam::123456789012:role/my-msk-connect-role"


@pytest.fixture
def mock_terraform_plan_parser() -> MagicMock:
    """Mock TerraformJsonPlanParser for testing."""
    mock_plan = MagicMock()
    mock_plan.resource_changes = []
    parser = MagicMock(spec=TerraformJsonPlanParser)
    parser.plan = mock_plan
    return parser


@pytest.fixture
def mock_aws_api() -> Iterator[MagicMock]:
    """Mock AWSApi for testing."""
    with patch("hooks.post_plan.AWSApi") as mock:
        yield mock


def _make_connector_change(subnets: list[str], security_groups: list[str]) -> MagicMock:
    """Helper to create a mock connector resource change."""
    return MagicMock(
        spec=ResourceChange,
        type="aws_mskconnect_connector",
        change=MagicMock(
            after={
                "kafka_cluster": [
                    {
                        "apache_kafka_cluster": [
                            {
                                "vpc": [
                                    {
                                        "subnets": subnets,
                                        "security_groups": security_groups,
                                    }
                                ]
                            }
                        ]
                    }
                ],
            },
            actions=[Action.ActionCreate],
        ),
    )


def _setup_iam_mocks(mock_aws_api: MagicMock) -> None:
    """Set up default IAM-related mocks so _validate_iam_permissions does not fail."""
    mock_aws_api.return_value.iam_client.get_role.return_value = {
        "Role": {"Arn": MOCK_ROLE_ARN}
    }
    mock_aws_api.return_value.simulate_principal_policy.return_value = {}


def test_msk_connect_plan_validator_validate_success(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test the full validate method with valid data."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True
    _setup_iam_mocks(mock_aws_api)

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert validator.validate()
    assert not validator.errors


def test_msk_connect_plan_validator_validate_failure_invalid_subnets(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure with missing subnets."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-missing"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in ["subnet-aaa", "subnet-bbb"]
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True
    _setup_iam_mocks(mock_aws_api)

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "subnet-missing" in validator.errors[0]


def test_msk_connect_plan_validator_validate_failure_security_group_vpc(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure with security group in wrong VPC."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-456"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True
    _setup_iam_mocks(mock_aws_api)

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert (
        "Security group sg-111 does not belong to the same VPC as the subnets"
        in validator.errors[0]
    )


def test_msk_connect_plan_validator_validate_failure_s3_object_missing(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure when S3 plugin object is missing."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = False
    _setup_iam_mocks(mock_aws_api)

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "S3 object" in validator.errors[0]
    assert "my-plugins-bucket" in validator.errors[0]


def test_msk_connect_plan_validator_validate_failure_s3_object_with_version(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test validation failure with S3 version info in error message."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = False
    _setup_iam_mocks(mock_aws_api)

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "version: abc123" in validator.errors[0]


def test_validate_iam_permissions_with_scoped_resources(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test that IAM validation uses resource-scoped ARNs from input data."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True
    _setup_iam_mocks(mock_aws_api)

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert validator.validate()

    # Verify simulate_principal_policy was called with resource-scoped ARNs
    # 3 kafka action groups + 1 S3 plugin + 1 CloudWatch
    calls = mock_aws_api.return_value.simulate_principal_policy.call_args_list
    expected_call_count = 5
    assert len(calls) == expected_call_count
    # Cluster actions (account from role ARN, region + msk_cluster from input)
    assert calls[0].kwargs["resource_arns"] == [
        "arn:aws:kafka:us-east-1:123456789012:cluster/app-int-example-01-msk/dummy-uuid"
    ]
    # Topic actions
    assert calls[1].kwargs["resource_arns"] == [
        "arn:aws:kafka:us-east-1:123456789012:topic/app-int-example-01-msk/dummy-uuid/test-topic"
    ]
    # Group actions
    assert calls[2].kwargs["resource_arns"] == [
        "arn:aws:kafka:us-east-1:123456789012:group/app-int-example-01-msk/dummy-uuid/test-group"
    ]


def test_validate_iam_permissions_missing_permission(
    ai_input: AppInterfaceInput,
    mock_terraform_plan_parser: MagicMock,
    mock_aws_api: MagicMock,
) -> None:
    """Test that missing IAM permissions are reported as errors."""
    subnets = ["subnet-aaa", "subnet-bbb", "subnet-ccc"]
    security_groups = ["sg-111"]
    mock_aws_api.return_value.get_subnets.return_value = [
        {"SubnetId": s, "VpcId": "vpc-123"} for s in subnets
    ]
    mock_aws_api.return_value.get_security_groups.return_value = [
        {"GroupId": sg, "VpcId": "vpc-123"} for sg in security_groups
    ]
    mock_aws_api.return_value.validate_s3_object.return_value = True
    _setup_iam_mocks(mock_aws_api)
    mock_aws_api.return_value.simulate_principal_policy.side_effect = [
        # Cluster actions: Connect denied
        {
            "kafka-cluster:Connect": "implicitDeny",
            "kafka-cluster:DescribeCluster": "allowed",
        },
        # Topic actions: all allowed
        {},
        # Group actions: all allowed
        {},
        # S3 plugin + CloudWatch: allowed
        {},
        {},
    ]

    mock_terraform_plan_parser.plan.resource_changes = [
        _make_connector_change(subnets, security_groups)
    ]

    validator = MskConnectPlanValidator(mock_terraform_plan_parser, ai_input)
    assert not validator.validate()
    assert len(validator.errors) == 1
    assert "kafka-cluster:Connect" in validator.errors[0]
    assert "implicitDeny" in validator.errors[0]

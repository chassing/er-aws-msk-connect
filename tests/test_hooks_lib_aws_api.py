from typing import TYPE_CHECKING

import pytest

from hooks_lib.aws_api import AWSApi

if TYPE_CHECKING:
    from unittest.mock import MagicMock


@pytest.fixture
def mock_botocore_config(mocker: MagicMock) -> MagicMock:
    """Mock BotocoreConfig."""
    return mocker.patch("hooks_lib.aws_api.BotocoreConfig")


@pytest.fixture
def mock_session(mocker: MagicMock) -> MagicMock:
    """Mock Session."""
    return mocker.patch("hooks_lib.aws_api.Session")


def test_aws_api_init(mock_session: MagicMock, mock_botocore_config: MagicMock) -> None:
    """Test AWSApi.__init__."""
    mock_session_instance = mock_session.return_value
    mock_config_instance = mock_botocore_config.return_value
    config_options = {"region_name": "us-east-1", "retries": {"max_attempts": 3}}

    api = AWSApi(config_options=config_options)

    mock_session.assert_called_once_with()
    assert api.session == mock_session_instance
    mock_botocore_config.assert_called_once_with(**config_options)
    assert api.config == mock_config_instance


@pytest.fixture
def aws_api(
    mock_session: MagicMock,
    mock_botocore_config: MagicMock,  # noqa: ARG001
) -> tuple[AWSApi, MagicMock]:
    """
    Fixture for AWSApi with mocked Session and BotocoreConfig.

    Returns the AWSApi instance and the session mock instance.
    """
    api = AWSApi(config_options={})
    return api, mock_session.return_value


def test_aws_api_ec2_client(aws_api: tuple[AWSApi, MagicMock]) -> None:
    """Test AWSApi.ec2_client property."""
    api, mock_session = aws_api
    client = api.ec2_client
    mock_session.client.assert_called_once_with("ec2", config=api.config)
    assert client == mock_session.client.return_value


def test_aws_api_s3_client(aws_api: tuple[AWSApi, MagicMock]) -> None:
    """Test AWSApi.s3_client property."""
    api, mock_session = aws_api
    client = api.s3_client
    mock_session.client.assert_called_once_with("s3", config=api.config)
    assert client == mock_session.client.return_value


@pytest.fixture
def mock_boto_client(mocker: MagicMock) -> MagicMock:
    """Fixture for a mocked boto3 client."""
    return mocker.MagicMock()


@pytest.fixture
def aws_api_with_mock_client(
    aws_api: tuple[AWSApi, MagicMock], mock_boto_client: MagicMock
) -> tuple[AWSApi, MagicMock]:
    """Fixture for AWSApi with a mocked client."""
    api, mock_session = aws_api
    mock_session.client.return_value = mock_boto_client
    return api, mock_boto_client


def test_get_subnets(aws_api_with_mock_client: tuple[AWSApi, MagicMock]) -> None:
    """Test AWSApi.get_subnets."""
    api, mock_client = aws_api_with_mock_client
    subnet_ids = ["subnet-1", "subnet-2"]
    expected_subnets = [{"SubnetId": "subnet-1"}, {"SubnetId": "subnet-2"}]
    mock_client.describe_subnets.return_value = {"Subnets": expected_subnets}

    subnets = api.get_subnets(subnets=subnet_ids)

    mock_client.describe_subnets.assert_called_once_with(SubnetIds=subnet_ids)
    assert subnets == expected_subnets


def test_get_security_groups(
    aws_api_with_mock_client: tuple[AWSApi, MagicMock],
) -> None:
    """Test AWSApi.get_security_groups."""
    api, mock_client = aws_api_with_mock_client
    sg_ids = ["sg-1", "sg-2"]
    expected_sgs = [{"GroupId": "sg-1"}, {"GroupId": "sg-2"}]
    mock_client.describe_security_groups.return_value = {"SecurityGroups": expected_sgs}

    sgs = api.get_security_groups(security_groups=sg_ids)

    mock_client.describe_security_groups.assert_called_once_with(GroupIds=sg_ids)
    assert sgs == expected_sgs


def test_validate_s3_object_success(
    aws_api_with_mock_client: tuple[AWSApi, MagicMock],
) -> None:
    """Test AWSApi.validate_s3_object success."""
    api, mock_client = aws_api_with_mock_client
    mock_client.head_object.return_value = {}

    result = api.validate_s3_object(bucket="my-bucket", key="my-key")

    mock_client.head_object.assert_called_once_with(Bucket="my-bucket", Key="my-key")
    assert result is True


def test_validate_s3_object_with_version(
    aws_api_with_mock_client: tuple[AWSApi, MagicMock],
) -> None:
    """Test AWSApi.validate_s3_object with version."""
    api, mock_client = aws_api_with_mock_client
    mock_client.head_object.return_value = {}

    result = api.validate_s3_object(bucket="my-bucket", key="my-key", version="v123")

    mock_client.head_object.assert_called_once_with(
        Bucket="my-bucket", Key="my-key", VersionId="v123"
    )
    assert result is True


def test_validate_s3_object_not_found(
    aws_api_with_mock_client: tuple[AWSApi, MagicMock],
) -> None:
    """Test AWSApi.validate_s3_object when object not found."""
    api, mock_client = aws_api_with_mock_client
    mock_client.head_object.side_effect = Exception("Not found")

    result = api.validate_s3_object(bucket="my-bucket", key="my-key")

    assert result is False

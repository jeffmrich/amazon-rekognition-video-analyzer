import os
from aws_cdk import core as cdk
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_kinesis as kinesis
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_iam as iam
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk.aws_lambda_event_sources import KinesisEventSource

class CdkStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB Table
        enriched_frame_table = dynamodb.Table(
            self,
            "EnrichedFrameTable",
            table_name="EnrichedFrame",
            partition_key=dynamodb.Attribute(
                name="frame_id",
                type=dynamodb.AttributeType.STRING
            ),
            read_capacity=10,
            write_capacity=10,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )
        enriched_frame_table.add_global_secondary_index(
            index_name="processed_year_month-processed_timestamp-index",
            projection_type=dynamodb.ProjectionType.ALL,
            read_capacity=10,
            write_capacity=10,
            partition_key=dynamodb.Attribute(
                name="processed_year_month",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="processed_timestamp",
                type=dynamodb.AttributeType.NUMBER
            )
        )

        # Create S3 Bucket for the image frames
        frame_bucket = s3.Bucket(
            self,
            "FrameS3Bucket",
            auto_delete_objects=True,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        # Create the image frame stream
        frame_stream = kinesis.Stream(
            self,
            "FrameStream",
            shard_count=1,
            stream_name="FrameStream"
        )

        # Create the Lambda to Process the images
        image_processor = _lambda.Function(
            self,
            "ImageProcessorLambda",
            function_name="imageprocessor",
            description="Function processes frame images fetched from a Kinesis stream.",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda/imageprocessor")),
            handler="index.lambda_handler",
            runtime=_lambda.Runtime.PYTHON_3_8,
            memory_size=128,
            timeout=cdk.Duration.seconds(60)
        )
        image_processor.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:CreateLogGroup",
                    "sns:publish",
                    "kinesis:GetRecords",
                    "kinesis:GetShardIterator",
                    "kinesis:ListStreams",
                    "kinesis:DescribeStream",
                    "rekognition:DetectLabels",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:DeleteObject"
                ],
                effect=iam.Effect.ALLOW,
                resources=["*"]
            )
        )
        image_processor.add_event_source(
            KinesisEventSource(
                starting_position=_lambda.StartingPosition.TRIM_HORIZON
            )
        )
        image_processor.node.add_dependency(frame_stream)

        # Create the Frame Fetcher Lambvda
        frame_fetcher = _lambda.Function(
            self,
            "FrameFetcherLambda",
            function_name="framefetcher",
            description="Function responds to a GET request by returning a list of frames up to a certain fetch horizon.",
            code=_lambda.Code.from_asset(os.path.join(os.path.dirname(__file__), "../lambda/framefetcher")),
            handler="index.lambda_handler",
            runtime=_lambda.Runtime.PYTHON_3_8,
            memory_size=128,
            timeout=cdk.Duration.seconds(60)
        )
        frame_fetcher.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:CreateLogGroup",
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:ListBucket",
                    "s3:DeleteObject"
                ],
                effect=iam.Effect.ALLOW,
                resources=["*"]
            )
        )

"""KnowledgeStack: curated corpus, S3 Vectors, and Bedrock Knowledge Base."""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrock as bedrock,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_s3 as s3,
)
from aws_cdk import (
    aws_s3_deployment as s3deploy,
)
from aws_cdk import (
    aws_s3vectors as s3vectors,
)
from constructs import Construct

from stacks.common import REPO_ROOT, tag_stack


class KnowledgeStack(cdk.Stack):
    """Deploy the complete, filterable RAG path used by AgentCore."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.corpus_bucket = s3.Bucket(
            self,
            "CulinaryCorpus",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,  # demo corpus, reproducible from git
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
        )

        staged_corpus = REPO_ROOT / ".cloud" / "corpus"
        if not Path(staged_corpus).exists():
            raise ValueError(
                "falta .cloud/corpus; ejecuta scripts/stage_bedrock_corpus.py antes de CDK"
            )
        self.corpus_deployment = s3deploy.BucketDeployment(
            self,
            "DeployCorpus",
            sources=[s3deploy.Source.asset(str(staged_corpus))],
            destination_bucket=self.corpus_bucket,
            destination_key_prefix="corpus",
            prune=True,
        )

        vector_bucket_name = f"chef-andino-vectors-{self.account}-{self.region}"
        vector_index_name = "chef-andino-culinary"
        self.vector_bucket = s3vectors.CfnVectorBucket(
            self,
            "VectorBucket",
            vector_bucket_name=vector_bucket_name,
        )
        self.vector_index = s3vectors.CfnIndex(
            self,
            "VectorIndex",
            vector_bucket_name=vector_bucket_name,
            index_name=vector_index_name,
            data_type="float32",
            dimension=1024,
            distance_metric="cosine",
        )
        self.vector_index.add_resource_dependency(self.vector_bucket)

        self.knowledge_role = iam.Role(
            self,
            "KnowledgeBaseRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="Acceso mínimo del Knowledge Base culinario",
        )
        self.corpus_bucket.grant_read(self.knowledge_role)
        embedding_model_arn = (
            f"arn:{self.partition}:bedrock:{self.region}::foundation-model/"
            "amazon.titan-embed-text-v2:0"
        )
        self.knowledge_role.add_to_policy(
            iam.PolicyStatement(actions=["bedrock:InvokeModel"], resources=[embedding_model_arn])
        )
        self.knowledge_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3vectors:*"],
                resources=[
                    self.vector_bucket.attr_vector_bucket_arn,
                    self.vector_index.attr_index_arn,
                ],
            )
        )
        vector_policy = s3vectors.CfnVectorBucketPolicy(
            self,
            "VectorBucketPolicy",
            vector_bucket_arn=self.vector_bucket.attr_vector_bucket_arn,
            policy={
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": self.knowledge_role.role_arn},
                        "Action": "s3vectors:*",
                        "Resource": [
                            self.vector_bucket.attr_vector_bucket_arn,
                            self.vector_index.attr_index_arn,
                        ],
                    }
                ],
            },
        )
        vector_policy.add_resource_dependency(self.vector_bucket)

        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "CulinaryKnowledgeBase",
            name="chef-andino-culinary",
            description="Corpus boliviano curado para la demostración Chef Andino",
            role_arn=self.knowledge_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=(
                    bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                        embedding_model_arn=embedding_model_arn,
                        embedding_model_configuration=(
                            bedrock.CfnKnowledgeBase.EmbeddingModelConfigurationProperty(
                                bedrock_embedding_model_configuration=(
                                    bedrock.CfnKnowledgeBase.BedrockEmbeddingModelConfigurationProperty(
                                        dimensions=1024,
                                        embedding_data_type="FLOAT32",
                                    )
                                )
                            )
                        ),
                    )
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="S3_VECTORS",
                s3_vectors_configuration=bedrock.CfnKnowledgeBase.S3VectorsConfigurationProperty(
                    index_arn=self.vector_index.attr_index_arn,
                    vector_bucket_arn=self.vector_bucket.attr_vector_bucket_arn,
                ),
            ),
        )
        self.knowledge_base.add_resource_dependency(self.vector_index)
        self.knowledge_base.add_resource_dependency(vector_policy)

        self.data_source = bedrock.CfnDataSource(
            self,
            "CorpusDataSource",
            name="chef-andino-corpus",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_deletion_policy="DELETE",
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.corpus_bucket.bucket_arn,
                    inclusion_prefixes=["corpus/"],
                ),
            ),
        )
        self.data_source.node.add_dependency(self.corpus_deployment)

        cdk.CfnOutput(self, "CorpusBucketName", value=self.corpus_bucket.bucket_name)
        cdk.CfnOutput(
            self,
            "KnowledgeBaseId",
            value=self.knowledge_base.attr_knowledge_base_id,
        )
        cdk.CfnOutput(self, "DataSourceId", value=self.data_source.attr_data_source_id)
        tag_stack(self)

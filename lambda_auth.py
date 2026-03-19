import boto3
import os
from botocore.config import Config

s3 = boto3.client(
    's3',
    region_name='eu-west-1',
    endpoint_url='https://s3.eu-west-1.amazonaws.com',
    config=Config(signature_version='s3v4')
)

def lambda_handler(event, context):
    headers = event.get('headers') or {}

    auth_recibida = headers.get('x-my-app-auth', '').strip()
    auth_esperada = os.environ['EXPECTED_AUTH'].strip()

    if not auth_recibida or auth_recibida != auth_esperada:
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "Unauthorized"}'
        }

    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': os.environ['BUCKET'],
            'Key': os.environ['KEY']
        },
        ExpiresIn=3600
    )

    return {
        "statusCode": 302,
        "headers": {"Location": url}
    }
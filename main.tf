provider "aws" {
  region = "eu-west-1"
}

# 1. Tu IP para seguridad del Proxy
data "http" "mi_ip" {
  url = "https://ipv4.icanhazip.com"
}

# 2. EC2 SOLO COMO PROXY SQUID
resource "aws_security_group" "proxy_sg" {
  name        = "proxy_sg_v3"
  description = "Permitir proxy solo desde mi IP"
  ingress {
    from_port   = 3128
    to_port     = 3128
    protocol    = "tcp"
    cidr_blocks = ["${chomp(data.http.mi_ip.response_body)}/32"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

resource "aws_instance" "mi_proxy" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t2.micro"
  vpc_security_group_ids = [aws_security_group.proxy_sg.id]
  user_data = <<-EOF
              #!/bin/bash
              apt-get update
              apt-get install -y squid
              sed -i 's/http_access deny all/http_access allow all/g' /etc/squid/squid.conf
              systemctl enable squid
              systemctl restart squid
              EOF
  tags = { Name = "Squid-Proxy-Only" }
}

# 3. LOS TRES BUCKETS S3 PRIVADOS (Host A, Host B y Host C)
resource "aws_s3_bucket" "bucket_a" { bucket_prefix = "host-a-token-" }
resource "aws_s3_bucket" "bucket_b" { bucket_prefix = "host-b-basic-" }
resource "aws_s3_bucket" "bucket_c" { bucket_prefix = "host-c-token2-" }

# Subir los archivos reales divididos (Han de estar en la misma carpeta que main.tf)
resource "aws_s3_object" "part1" {
  bucket = aws_s3_bucket.bucket_a.id
  key    = "debian-13.2.0-amd64-netinst.7z.001"
  source = "debian-13.2.0-amd64-netinst.7z.001" 
}

resource "aws_s3_object" "part2" {
  bucket = aws_s3_bucket.bucket_b.id
  key    = "debian-13.2.0-amd64-netinst.7z.002"
  source = "debian-13.2.0-amd64-netinst.7z.002"
}

resource "aws_s3_object" "part3" {
  bucket = aws_s3_bucket.bucket_c.id
  key    = "debian-13.2.0-amd64-netinst.7z.003"
  source = "debian-13.2.0-amd64-netinst.7z.003"
}

# 4. LAMBDAS PARA AUTENTICACIÓN Y REDIRECCIÓN S3
resource "aws_iam_role" "lambda_role" {
  name = "lambda_s3_auth_role_v3" 
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_s3_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda_auth.py"
  output_path = "${path.module}/lambda_auth.zip"
}

# --- LAMBDA 1 (TOKEN) ---
resource "aws_lambda_function" "auth_token_1" {
  function_name    = "auth_token_host_a"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_auth.lambda_handler"
  runtime          = "python3.9"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  environment {
    variables = {
      EXPECTED_AUTH = "Bearer MI_TOKEN_SECRETO_123"
      BUCKET        = aws_s3_bucket.bucket_a.id
      KEY           = aws_s3_object.part1.key
    }
  }
}

# --- LAMBDA 2 (BASIC) ---
resource "aws_lambda_function" "auth_basic_2" {
  function_name    = "auth_basic_host_b"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_auth.lambda_handler"
  runtime          = "python3.9"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  environment {
    variables = {
      EXPECTED_AUTH = "Basic YWRtaW46c3VwZXJzZWNyZXRvMTIz" # admin:supersecreto123 en base64
      BUCKET        = aws_s3_bucket.bucket_b.id
      KEY           = aws_s3_object.part2.key
    }
  }
}

# --- LAMBDA 3 (TOKEN 2) ---
resource "aws_lambda_function" "auth_token_3" {
  function_name    = "auth_token_host_c"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_auth.lambda_handler"
  runtime          = "python3.9"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  environment {
    variables = {
      EXPECTED_AUTH = "Bearer TOKEN_DEBIAN_3"
      BUCKET        = aws_s3_bucket.bucket_c.id
      KEY           = aws_s3_object.part3.key
    }
  }
}

# 5. LOS TRES API GATEWAYS
# --- GATEWAY 1 (Token) ---
resource "aws_apigatewayv2_api" "api_gateway_1" {
  name          = "api-gateway-token-1"
  protocol_type = "HTTP"
  # Sin 'target': gestionamos la integración manualmente
}

resource "aws_apigatewayv2_integration" "int_1" {
  api_id                 = aws_apigatewayv2_api.api_gateway_1.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth_token_1.invoke_arn
  payload_format_version = "2.0"  # Garantiza event['headers'] como dict en la Lambda
}

resource "aws_apigatewayv2_route" "route_1" {
  api_id    = aws_apigatewayv2_api.api_gateway_1.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.int_1.id}"
}

resource "aws_apigatewayv2_stage" "stage_1" {
  api_id      = aws_apigatewayv2_api.api_gateway_1.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw_1" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_token_1.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api_gateway_1.execution_arn}/*/*"
}

# --- GATEWAY 2 (Basic) ---
resource "aws_apigatewayv2_api" "api_gateway_2" {
  name          = "api-gateway-basic-2"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "int_2" {
  api_id                 = aws_apigatewayv2_api.api_gateway_2.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth_basic_2.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "route_2" {
  api_id    = aws_apigatewayv2_api.api_gateway_2.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.int_2.id}"
}

resource "aws_apigatewayv2_stage" "stage_2" {
  api_id      = aws_apigatewayv2_api.api_gateway_2.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw_2" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_basic_2.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api_gateway_2.execution_arn}/*/*"
}

# --- GATEWAY 3 (Token 2) ---
resource "aws_apigatewayv2_api" "api_gateway_3" {
  name          = "api-gateway-token-3"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "int_3" {
  api_id                 = aws_apigatewayv2_api.api_gateway_3.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.auth_token_3.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "route_3" {
  api_id    = aws_apigatewayv2_api.api_gateway_3.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.int_3.id}"
}

resource "aws_apigatewayv2_stage" "stage_3" {
  api_id      = aws_apigatewayv2_api.api_gateway_3.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "api_gw_3" {
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auth_token_3.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api_gateway_3.execution_arn}/*/*"
}

# --- OUTPUTS PARA EL JSON ---
output "ip_y_puerto_de_tu_proxy" { value = "${aws_instance.mi_proxy.public_ip}:3128" }
output "api_gateway_1_token" { value = aws_apigatewayv2_api.api_gateway_1.api_endpoint }
output "api_gateway_2_basic" { value = aws_apigatewayv2_api.api_gateway_2.api_endpoint }
output "api_gateway_3_token" { value = aws_apigatewayv2_api.api_gateway_3.api_endpoint }
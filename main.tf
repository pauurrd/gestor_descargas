provider "aws" {
  region = "eu-west-1" 
}

# 1. Tu IP para seguridad
data "http" "mi_ip" {
  url = "https://ipv4.icanhazip.com"
}

# 2. Grupo de Seguridad (Proxy + Web)
resource "aws_security_group" "proxy_sg" {
  name        = "proxy_security_group_v2"
  description = "Permitir proxy y web solo desde mi IP"

  # Puerto del Proxy (Squid)
  ingress {
    from_port   = 3128
    to_port     = 3128
    protocol    = "tcp"
    cidr_blocks = ["${chomp(data.http.mi_ip.response_body)}/32"]
  }

  # Puerto Web (Para la descarga con Usuario/Contraseña)
  ingress {
    from_port   = 80
    to_port     = 80
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

# 3. Imagen de Ubuntu
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# 4. Servidor EC2 (Proxy + Archivos con Autenticaciones)
resource "aws_instance" "mi_proxy" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = "t2.micro"
  vpc_security_group_ids = [aws_security_group.proxy_sg.id]

  user_data = <<-EOF
              #!/bin/bash
              apt-get update
              apt-get install -y squid nginx apache2-utils zip
              
              # Configurar e iniciar Proxy (Permitir tráfico externo)
              sed -i 's/http_access deny all/http_access allow all/g' /etc/squid/squid.conf
              systemctl enable squid
              systemctl restart squid

              # --- CONFIGURACIÓN DE NGINX ---
              
              # 1. Preparar Autenticación Básica
              htpasswd -bc /etc/nginx/.htpasswd admin supersecreto123

              # 2. Configurar Nginx con las dos rutas (Basic y Token)
              cat << 'EOC' > /etc/nginx/sites-available/default
              server {
                  listen 80 default_server;
                  root /var/www/html;
                  
                  # Ruta protegida por Token Bearer
                  location /api_segura/ {
                      if ($http_authorization != "Bearer MI_TOKEN_SECRETO_123") {
                          return 401;
                      }
                  }

                  # Ruta protegida por Auth Basic (Por defecto)
                  location / {
                      auth_basic "Area Restringida de Descargas";
                      auth_basic_user_file /etc/nginx/.htpasswd;
                  }
              }
              EOC
              systemctl restart nginx

              # --- CREACIÓN DE ARCHIVOS DE PRUEBA ---
              cd /var/www/html
              
              # Archivo para Auth Basic
              echo "Este es un documento muy secreto" > secreto.txt
              zip protegido_auth.zip secreto.txt
              
              # Archivo para Token Bearer
              mkdir -p api_segura
              echo "¡Éxito! Has descargado el archivo usando un Token Bearer nativo." > api_segura/archivo6_token.txt
              
              rm index.nginx-debian.html
              EOF

  tags = {
    Name = "Proxy-Y-Web-Pruebas"
  }
}

# 5. Configuración del Bucket S3
resource "aws_s3_bucket" "archivos_prueba" {
  bucket_prefix = "gestor-descargas-"
}

# Desbloquear acceso público para los 3 archivos que lo necesitan
resource "aws_s3_bucket_ownership_controls" "permisos" {
  bucket = aws_s3_bucket.archivos_prueba.id
  rule { object_ownership = "BucketOwnerPreferred" }
}
resource "aws_s3_bucket_public_access_block" "permisos" {
  bucket = aws_s3_bucket.archivos_prueba.id
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# 6. ARCHIVO 1: TXT (Público)
resource "aws_s3_object" "archivo1_txt" {
  depends_on = [aws_s3_bucket_ownership_controls.permisos, aws_s3_bucket_public_access_block.permisos]
  bucket  = aws_s3_bucket.archivos_prueba.id
  key     = "archivo1_publico.txt"
  content = "Contenido del TXT publico"
  acl     = "public-read"
}

# 7. ARCHIVO 2: PDF (Público)
resource "aws_s3_object" "archivo2_pdf" {
  depends_on = [aws_s3_bucket_ownership_controls.permisos, aws_s3_bucket_public_access_block.permisos]
  bucket  = aws_s3_bucket.archivos_prueba.id
  key     = "archivo2_publico.pdf"
  content = "Simulacion de PDF publico" # Nota: Es texto simulando ser PDF para que pese poco en la prueba
  acl     = "public-read"
}

# 8. ARCHIVO 3: ZIP (Público)
resource "aws_s3_object" "archivo3_zip" {
  depends_on = [aws_s3_bucket_ownership_controls.permisos, aws_s3_bucket_public_access_block.permisos]
  bucket  = aws_s3_bucket.archivos_prueba.id
  key     = "archivo3_publico.zip"
  content = "Simulacion de ZIP publico"
  acl     = "public-read"
}

# 9. ARCHIVO 4: PDF (Requiere Token)
resource "aws_s3_object" "archivo4_pdf_token" {
  bucket  = aws_s3_bucket.archivos_prueba.id
  key     = "archivo4_token.pdf"
  content = "Simulacion de PDF protegido por token"
  # NO le ponemos public-read, por lo que es privado por defecto.
}

# --- OUTPUTS PARA QUE PUEDAS PROBAR ---

output "ip_y_puerto_de_tu_proxy" {
  value = "${aws_instance.mi_proxy.public_ip}:3128"
}

output "url_1_txt_publico" {
  value = "https://${aws_s3_bucket.archivos_prueba.bucket_regional_domain_name}/${aws_s3_object.archivo1_txt.key}"
}

output "url_2_pdf_publico" {
  value = "https://${aws_s3_bucket.archivos_prueba.bucket_regional_domain_name}/${aws_s3_object.archivo2_pdf.key}"
}

output "url_3_zip_publico" {
  value = "https://${aws_s3_bucket.archivos_prueba.bucket_regional_domain_name}/${aws_s3_object.archivo3_zip.key}"
}

output "instrucciones_4_pdf_token" {
  value = "Este archivo es privado. Para generar la URL con el Token (Presigned URL) que dura 1 hora, abre tu terminal y ejecuta: aws s3 presign s3://${aws_s3_bucket.archivos_prueba.id}/${aws_s3_object.archivo4_pdf_token.key} --expires-in 3600 --region eu-west-1"
}

output "url_5_zip_usuario_y_contrasena" {
  value = "http://${aws_instance.mi_proxy.public_ip}/protegido_auth.zip (Usuario: admin | Contraseña: supersecreto123)"
}

output "url_6_txt_token_bearer" {
  value = "http://${aws_instance.mi_proxy.public_ip}/api_segura/archivo6_token.txt (Token Bearer: MI_TOKEN_SECRETO_123)"
}
resource "aws_vpc" "cdc_mysql" {
  cidr_block = "10.0.0.0/16"
  instance_tenancy = "default"
  enable_dns_hostnames = true
  
  tags = {
    Name = "cdc mysql"
  } 
}

resource "aws_subnet" "private-2a" {
  vpc_id     = aws_vpc.cdc_mysql.id
  cidr_block = "10.0.1.0/24"
  availability_zone = "us-east-2a"

  tags = {
    Name = "private-2a"
  }
}

resource "aws_subnet" "private-2b" {
  vpc_id     = aws_vpc.cdc_mysql.id
  cidr_block = "10.0.2.0/24"
  availability_zone = "us-east-2b"

  tags = {
    Name = "private-2b"
  }
}

resource "aws_subnet" "public-2a" {
  vpc_id     = aws_vpc.cdc_mysql.id
  cidr_block = "10.0.3.0/24"
  availability_zone = "us-east-2a"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-2a"
  }
}

resource "aws_subnet" "public-2b" {
  vpc_id     = aws_vpc.cdc_mysql.id
  cidr_block = "10.0.4.0/24"
  availability_zone = "us-east-2b"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-2b"
  }
}

resource "aws_default_route_table" "main-public-rt" {
  default_route_table_id = aws_vpc.cdc_mysql.default_route_table_id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.internet_gateway.id
  }

  tags = {
    Name = "main-public-rt"
  }
}

resource "aws_route_table" "private-rt" {
  vpc_id = aws_vpc.cdc_mysql.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_nat_gateway.public_nat_gateway.id
  }

  tags = {
    Name = "private-rt"
  }
}

resource "aws_route_table_association" "private-rt-2a-association" {
  subnet_id      = aws_subnet.private-2a.id
  route_table_id = aws_route_table.private-rt.id
}

resource "aws_route_table_association" "private-rt-2b-association" {
  subnet_id      = aws_subnet.private-2b.id
  route_table_id = aws_route_table.private-rt.id
}


resource "aws_internet_gateway" "internet_gateway" {
  vpc_id = aws_vpc.cdc_mysql.id

  tags = {
    Name = "internet_gateway"
  }
}

# resource "aws_eip" "ec2_eip" {
#   vpc = true

#   depends_on = [
#     aws_internet_gateway.internet_gateway
#   ]
# }

resource "aws_eip" "nat_gateway_eip" {
  depends_on = [
    aws_internet_gateway.internet_gateway
  ]
}

resource "aws_nat_gateway" "public_nat_gateway" {
  allocation_id = aws_eip.nat_gateway_eip.id
  subnet_id = aws_subnet.public-2a.id
  
  tags = {
    "Name" = "public_nat_gateway"
  }
  
  depends_on = [
    aws_internet_gateway.internet_gateway
  ]
}
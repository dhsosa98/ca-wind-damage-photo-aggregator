# Wind-Damage Photo Aggregator - Makefile

.PHONY: deploy destroy clean build push docker-build docker-push

# Get AWS account ID and region
AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --query Account --output text)
AWS_REGION := $(shell aws configure get region)
ECR_REPO := wind-damage-aggregator
IMAGE_TAG := latest


# Build Docker image
docker-build:
	@echo "Building Docker image..."
	docker build -t $(ECR_REPO):$(IMAGE_TAG) .
	@echo "Docker image built successfully!"

# Login to ECR
ecr-login:
	@echo "Logging in to ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

# Push Docker image to ECR
docker-push: ecr-login
	@echo "Pushing Docker image to ECR..."
	aws ecr create-repository --repository-name $(ECR_REPO) --region $(AWS_REGION) || true
	docker tag $(ECR_REPO):$(IMAGE_TAG) $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):$(IMAGE_TAG)
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO):$(IMAGE_TAG)
	@echo "Docker image pushed successfully!"

# Build and push Docker image
build: docker-build docker-push

# Deploy the entire infrastructure
deploy: build
	@echo "Deploying Wind-Damage Photo Aggregator..."
	cd iac && terraform init
	cd iac && terraform apply -auto-approve -var="gemini_api_key=$(GEMINI_API_KEY)"
	@echo "Deployment complete!"

# Destroy all infrastructure
destroy:
	@echo "Destroying infrastructure..."
	cd iac && terraform destroy -auto-approve
	@echo "Infrastructure destroyed!"

# Clean up temporary files
clean:
	@echo "Cleaning up..."
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +
	rm -rf .terraform/
	docker rmi $(ECR_REPO):$(IMAGE_TAG) 2>/dev/null || true
	@echo "Cleanup complete!"

# Show API endpoint
endpoint:
	@echo "Getting API endpoint..."
	cd iac && terraform output -raw api_endpoint

# Show ECR repository URL
ecr-url:
	@echo "ECR Repository URL:"
	cd iac && terraform output -raw ecr_repository_url

# Run local development with extended timeout
local-dev:
	@echo "Starting local development with 15-minute timeout..."
	docker-compose up --build 
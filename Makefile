CURRENT_DIR = $(shell pwd)
PROJECT_NAME = pickupartist
PORT = 8080
include .env
export

build-network:
	docker network create service_network -d bridge || true

build:
	docker build -t ${PROJECT_NAME}:dev .

build-frontend:
	docker build -f Dockerfile.streamlit -t ${PROJECT_NAME}:frontend .

run: build-network
	docker run -it --rm \
	    --env-file ${CURRENT_DIR}/.env \
	    -p ${FASTAPI_PORT}:${FASTAPI_PORT} \
	    -v "${CURRENT_DIR}/src:/srv/src" \
	    -v "${CURRENT_DIR}/data:/srv/data" \
		--network service_network \
	    --name ${PROJECT_NAME}_container \
	    ${PROJECT_NAME}:dev serve

run-debug:
	docker run -it --rm \
	    --env-file ${CURRENT_DIR}/.env \
	    -v "${CURRENT_DIR}/src:/srv/src" \
	    -v "${CURRENT_DIR}/data:/srv/data" \
	    --name ${PROJECT_NAME}_container \
	    ${PROJECT_NAME}:dev bash

stop:
	docker rm -f ${PROJECT_NAME}_container

run-frontend: build-network
	docker run -d --rm \
	    --env-file ${CURRENT_DIR}/.env \
	    -p ${STREAMLIT_PORT}:${STREAMLIT_PORT} \
	    -v "${CURRENT_DIR}/frontend_app:/srv/src" \
		--network service_network \
	    --name ${PROJECT_NAME}_frontend \
	    ${PROJECT_NAME}:frontend
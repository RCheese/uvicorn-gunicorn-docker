import os
import time
from pathlib import Path, PurePath

import docker
import pytest
import requests

from ..utils import (
    CONTAINER_NAME,
    IMAGE_NAME,
    get_config,
    get_logs,
    remove_previous_container,
)

client = docker.from_env()


def verify_container(container, response_text, prestart_str):
    config_data = get_config(container)
    assert config_data["workers_per_core"] == 1
    assert config_data["host"] == "0.0.0.0"
    assert config_data["port"] == "80"
    assert config_data["loglevel"] == "info"
    assert config_data["workers"] >= 2
    assert config_data["bind"] == "0.0.0.0:80"
    logs = get_logs(container)
    assert prestart_str in logs
    response = requests.get("http://127.0.0.1:8000")
    assert response.text == response_text


@pytest.mark.parametrize(
    "environment,prestart_str",
    [
        (
            {"MODULE_NAME": "custom_app.custom_main", "VARIABLE_NAME": "custom_var"},
            "Running inside /app/prestart.sh, you could add migrations to this file",
        ),
        (
            {"APP_MODULE": "custom_app.custom_main:custom_var"},
            "Running inside /app/prestart.sh, you could add migrations to this file",
        ),
        (
            {
                "MODULE_NAME": "custom_app.custom_main",
                "VARIABLE_NAME": "custom_var",
                "PRE_START_PATH": "/app/custom_app/custom-prestart.sh",
            },
            "Custom prestart script",
        ),
        (
            {
                "APP_MODULE": "custom_app.custom_main:custom_var",
                "PRE_START_PATH": "/app/custom_app/custom-prestart.sh",
            },
            "Custom prestart script",
        ),
    ],
)
def test_custom_app(environment, prestart_str):
    name = os.getenv("NAME")
    dockerfile = f"{name}.dockerfile"
    response_text = os.getenv("TEST_STR2")
    sleep_time = int(os.getenv("SLEEP_TIME", 1))
    remove_previous_container(client)
    test_path: PurePath = Path(__file__)
    path = test_path.parent / "custom_app"
    client.images.build(path=str(path), dockerfile=dockerfile, tag=IMAGE_NAME)
    container = client.containers.run(
        IMAGE_NAME,
        name=CONTAINER_NAME,
        environment=environment,
        ports={"80": "8000"},
        detach=True,
    )
    time.sleep(sleep_time)
    verify_container(container, response_text, prestart_str)
    container.stop()
    # Test that everything works after restarting too
    container.start()
    time.sleep(sleep_time)
    verify_container(container, response_text, prestart_str)
    container.stop()
    container.remove()

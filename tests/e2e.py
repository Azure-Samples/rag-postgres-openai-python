import socket
import time
from collections.abc import Generator
from contextlib import closing
from multiprocessing import Process

import pytest
import requests
import uvicorn
from playwright.sync_api import Page, Route, expect

import fastapi_app as app

expect.set_options(timeout=10_000)


def wait_for_server_ready(url: str, timeout: float = 10.0, check_interval: float = 0.5) -> bool:
    """Make requests to provided url until it responds without error."""
    conn_error = None
    for _ in range(int(timeout / check_interval)):
        try:
            requests.get(url)
        except requests.ConnectionError as exc:
            time.sleep(check_interval)
            conn_error = str(exc)
        else:
            return True
    raise RuntimeError(conn_error)


@pytest.fixture(scope="session")
def free_port() -> int:
    """Returns a free port for the test server to bind."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def run_server(port: int):
    uvicorn.run(app.create_app(testing=True), port=port)


@pytest.fixture()
def live_server_url(mock_session_env, free_port: int) -> Generator[str, None, None]:
    proc = Process(target=run_server, args=(free_port,), daemon=True)
    proc.start()
    url = f"http://localhost:{free_port}/"
    wait_for_server_ready(url, timeout=10.0, check_interval=0.5)
    yield url
    proc.kill()


def test_home(page: Page, live_server_url: str):
    page.goto(live_server_url)
    expect(page).to_have_title("RAG on PostgreSQL")


def test_chat(page: Page, live_server_url: str):
    # Set up a mock route to the /chat endpoint with streaming results
    def handle(route: Route):
        # Assert that session_state is specified in the request (None for now)
        if route.request.post_data_json:
            session_state = route.request.post_data_json["sessionState"]
            assert session_state is None
        # Read the JSONL from our snapshot results and return as the response
        f = open(
            "tests/snapshots/test_api_routes/test_advanced_chat_streaming_flow/advanced_chat_streaming_flow_response.jsonlines"
        )
        jsonl = f.read()
        f.close()
        route.fulfill(body=jsonl, status=200, headers={"Transfer-encoding": "Chunked"})

    page.route("*/**/chat/stream", handle)

    # Check initial page state
    page.goto(live_server_url)
    expect(page).to_have_title("RAG on PostgreSQL")
    expect(page.get_by_role("heading", name="Product chat")).to_be_visible()
    expect(page.get_by_role("button", name="Clear chat")).to_be_disabled()
    expect(page.get_by_role("button", name="Developer settings")).to_be_enabled()

    # Ask a question and wait for the message to appear
    page.get_by_placeholder("Type a new question (e.g. does my plan cover annual eye exams?)").click()
    page.get_by_placeholder("Type a new question (e.g. does my plan cover annual eye exams?)").fill(
        "Whats the dental plan?"
    )
    page.get_by_role("button", name="Ask question button").click()

    expect(page.get_by_text("Whats the dental plan?")).to_be_visible()
    expect(page.get_by_text("The capital of France is Paris.")).to_be_visible()
    expect(page.get_by_role("button", name="Clear chat")).to_be_enabled()

    # Show the thought process
    page.get_by_label("Show thought process").click()
    expect(page.get_by_title("Thought process")).to_be_visible()
    expect(page.get_by_text("Prompt to generate search arguments")).to_be_visible()

    # Clear the chat
    page.get_by_role("button", name="Clear chat").click()
    expect(page.get_by_text("Whats the dental plan?")).not_to_be_visible()
    expect(page.get_by_text("The capital of France is Paris.")).not_to_be_visible()
    expect(page.get_by_role("button", name="Clear chat")).to_be_disabled()


def test_chat_customization(page: Page, live_server_url: str):
    # Set up a mock route to the /chat endpoint
    def handle(route: Route):
        if route.request.post_data_json:
            overrides = route.request.post_data_json["context"]["overrides"]
            assert overrides["use_advanced_flow"] is False
            assert overrides["retrieval_mode"] == "vectors"
            assert overrides["top"] == 1
            assert overrides["prompt_template"] == "You are a cat and only talk about tuna."

        # Read the JSON from our snapshot results and return as the response
        f = open("tests/snapshots/test_api_routes/test_simple_chat_flow/simple_chat_flow_response.json")
        json = f.read()
        f.close()
        route.fulfill(body=json, status=200)

    page.route("*/**/chat", handle)

    # Check initial page state
    page.goto(live_server_url)
    expect(page).to_have_title("RAG on PostgreSQL")

    # Customize all the settings
    page.get_by_role("button", name="Developer settings").click()
    page.get_by_text(
        "Use advanced flow with query rewriting and filter formulation. Not compatible with Ollama models."
    ).click()
    page.get_by_label("Retrieve this many matching rows:").click()
    page.get_by_label("Retrieve this many matching rows:").fill("1")
    page.get_by_text("Vectors + Text (Hybrid)").click()
    page.get_by_role("option", name="Vectors", exact=True).click()
    page.get_by_label("Override prompt template").click()
    page.get_by_label("Override prompt template").fill("You are a cat and only talk about tuna.")

    page.get_by_text("Stream chat completion responses").click()
    page.locator("button").filter(has_text="Close").click()

    # Ask a question and wait for the message to appear
    page.get_by_placeholder("Type a new question (e.g. does my plan cover annual eye exams?)").click()
    page.get_by_placeholder("Type a new question (e.g. does my plan cover annual eye exams?)").fill(
        "Whats the dental plan?"
    )
    page.get_by_role("button", name="Ask question button").click()

    expect(page.get_by_text("Whats the dental plan?")).to_be_visible()
    expect(page.get_by_text("The capital of France is Paris.")).to_be_visible()
    expect(page.get_by_role("button", name="Clear chat")).to_be_enabled()


def test_chat_nonstreaming(page: Page, live_server_url: str):
    # Set up a mock route to the /chat_stream endpoint
    def handle(route: Route):
        # Read the JSON from our snapshot results and return as the response
        f = open("tests/snapshots/test_api_routes/test_advanced_chat_flow/advanced_chat_flow_response.json")
        json = f.read()
        f.close()
        route.fulfill(body=json, status=200)

    page.route("*/**/chat", handle)

    # Check initial page state
    page.goto(live_server_url)
    expect(page).to_have_title("RAG on PostgreSQL")
    expect(page.get_by_role("button", name="Developer settings")).to_be_enabled()
    page.get_by_role("button", name="Developer settings").click()
    page.get_by_text("Stream chat completion responses").click()
    page.locator("button").filter(has_text="Close").click()

    # Ask a question and wait for the message to appear
    page.get_by_placeholder("Type a new question (e.g. does my plan cover annual eye exams?)").click()
    page.get_by_placeholder("Type a new question (e.g. does my plan cover annual eye exams?)").fill(
        "Whats the dental plan?"
    )
    page.get_by_label("Ask question button").click()

    expect(page.get_by_text("Whats the dental plan?")).to_be_visible()
    expect(page.get_by_text("The capital of France is Paris.")).to_be_visible()
    expect(page.get_by_role("button", name="Clear chat")).to_be_enabled()

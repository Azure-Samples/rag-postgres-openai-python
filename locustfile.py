import random
import time

from locust import HttpUser, between, task


class ChatUser(HttpUser):
    wait_time = between(5, 20)

    @task
    def ask_question(self):
        self.client.get("/")
        time.sleep(5)
        self.client.post(
            "/chat",
            json={
                "messages": [
                    {
                        "content": random.choice(
                            ["Best shoe for hiking?", "Climbing shoe cheaper than $30?", "Waterproof camping gear?"]
                        ),
                        "role": "user",
                    }
                ],
                "context": {
                    "overrides": {"use_advanced_flow": True, "top": 3, "retrieval_mode": "hybrid", "temperature": 0.3}
                },
            },
        )
        time.sleep(5)
        self.client.post(
            "/chat",
            json={
                "messages": [
                    {"content": "Best shoe for hiking?", "role": "user"},
                    {
                        "content": "For the best shoe for hiking, I recommend the Trailblaze Steel-Blue Hiking Shoes.",
                        "role": "assistant",
                    },
                    {"content": "any other options?", "role": "user"},
                ],
                "context": {
                    "overrides": {"use_advanced_flow": True, "top": 3, "retrieval_mode": "hybrid", "temperature": 0.3}
                },
            },
        )

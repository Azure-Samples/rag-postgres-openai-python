const BACKEND_URI = "";

import { ChatAppRequest } from "./models";

export async function chatApi(request: ChatAppRequest): Promise<Response> {
    return await fetch(`${BACKEND_URI}/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(request)
    });
}
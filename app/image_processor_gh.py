"""
Image processor for GitHub Actions using GitHub Copilot Models API.
Handles image and text completion via GitHub Models.
"""

import logging

logger = logging.getLogger(__name__)


def execute_image_completion(client, encoded_image, system_prompt, model="openai/gpt-4.1", temperature=0):
    """
    Executes a chat completion based on the system prompt and encoded image.

    Args:
        client: The OpenAI client object.
        encoded_image (str): The base64 encoded image.
        system_prompt (str): The system prompt.
        model (str): The model name (default: openai/gpt-4.1).
        temperature (float, optional): The temperature of the completion. Defaults to 0.

    Returns:
        str: The generated response from the chat completion.
    """

    if client is None:
        logger.error("client parameter is required.")
        raise ValueError("client parameter is required.")
    if encoded_image is None:
        logger.error("encoded_image parameter is required.")
        raise ValueError("encoded_image parameter is required.")
    if system_prompt is None:
        logger.error("system_prompt parameter is required.")
        raise ValueError("system_prompt parameter is required.")

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{encoded_image}"
                    }
                }
            ]
        }
    ]

    logger.info("Executing image completion...")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )

    return response.choices[0].message.content


def execute_text_completion(client, text, system_prompt, model="openai/gpt-4.1", temperature=0.3):
    """
    Executes a chat completion based on the system prompt and text input.

    Args:
        client: The OpenAI client object.
        text (str): The user text input.
        system_prompt (str): The system prompt.
        model (str): The model name (default: openai/gpt-4.1).
        temperature (float, optional): The temperature of the completion. Defaults to 0.3.

    Returns:
        str: The generated response from the chat completion.
    """

    if client is None:
        logger.error("client parameter is required.")
        raise ValueError("client parameter is required.")
    if text is None:
        logger.error("text parameter is required.")
        raise ValueError("text parameter is required.")
    if system_prompt is None:
        logger.error("system_prompt parameter is required.")
        raise ValueError("system_prompt parameter is required.")

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": text
        }
    ]

    logger.info("Executing text completion...")
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature
    )

    return response.choices[0].message.content


def read_file(file_path):
    """
    Reads the contents of a file and returns it as a string.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The contents of the file as a string.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    return content


import base64
import os
import mimetypes
from pathlib import Path
from together import Together
from typing import Dict, Any
from data.database_postgres import (
    get_fitness_goal_diet_gender_age_time_deadline, daily_height_weight_diet_hist, store_chat_postgres
    )

debug = True

def get_image_description(image_path: str="temp/download.jpeg", prompt: str = " ", user_id: int = 1) -> Dict[str, Any]:
    """
    Takes an image path (PNG, JPG, JPEG, ICO) and returns an image description using LLaMA 3.2 Vision.
    
    Args:
        image_path (str): Path to the image file (png, jpg, jpeg, ico)
        prompt (str): Additional prompt for the AI
        user_id (int): User ID for fetching personal data
        
    Returns:
        Dict containing 'status' ('success' or 'error') and 'description' or 'message'
    """
    try:
        # Get user's fitness data
        fitness_goal, diet_pref, gender, name, age, medical_cond, time_deadline, conn, cur   = get_fitness_goal_diet_gender_age_time_deadline(user_id)
        # if debug: print("no Problem detected here 0")
        height, weight, diet_history = daily_height_weight_diet_hist(user_id,conn, cur)
        # if debug: print("no Problem detected here 1")
        age = str(age)
        gender = str(gender)
        fitness_goal = str(fitness_goal)
        diet_pref = str(diet_pref)
        time_deadline = str(time_deadline)
        personalized_info = (
            f"User Information:\n"
            f"Name: {name}\n"
            f"Diet preferences: {diet_pref}\n"
            f"Age: {age}\n"
            f"(Your given output should be properly formatted markdown, addressed to the user, make no mistakes!)"
        )
        prompt = f"User Prompt:\n"+prompt + personalized_info
        if debug: print(" no Problem detected here 2")
        
        message_content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        together_api_key = str(os.getenv("TOGETHER_API_KEY"))
        client = Together(api_key=together_api_key)
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            messages=[{"role": "user", "content": message_content}],
            max_tokens=int(os.getenv("LARGE_TOKENS")),
            temperature=float(os.getenv("temperature__T"))
        )
        description = response.choices[0].message.content.strip()
        if debug: print(description)
        store_chat_postgres(user_id=user_id, user_prompt=prompt, response=description, has_image=True)
        return {"status":"success", "description": description}
    except Exception as e:
        return {"status":"error", "message": str(e)}
# Example usage:
# result = get_image_description("temp/download.jpeg", user_id=1, prompt = "") 

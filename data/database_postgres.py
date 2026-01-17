'''
Database handler for the project.
This header provides functions to interact with the PostgreSQL database,
including profile management, daily stats and history viewing, and other storage functionalities.
'''
import os
import threading
debug = True  







# Chat History Storage
def store_chat_postgres( user_prompt:str, response:str):
    return False

# Example usage:
# history = get_chat_history_by_date(1, 2024, 12, 15)
# for chat in history:
#     print(f"User: {chat['user_prompt']}")
#     print(f"System: {chat['system_response']}")
#functions ----------------------------------------------------------------------------------------------
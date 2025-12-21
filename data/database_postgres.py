'''
Database handler for the project.
This header provides functions to interact with the PostgreSQL database,
including user registration, profile management, daily stats, and other storage functionalities.
'''
import psycopg2
from datetime import datetime, timedelta, time
import os
import threading
debug = True  

def connect_db():
    # Establish connection to PostgreSQL
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT")
    )
    cur = conn.cursor()
    return conn, cur
def close_db(conn, cur):
    cur.close()
    conn.close()
    if debug: print("Database connection closed.")
def get_fitness_goal_diet_gender_age_time_deadline(user_id: int):
    conn, cur = connect_db()
    try:
        cur.execute("SELECT fitness_goal, diet_pref, (user_information).gender, (user_information).name, (user_information).age, medical_conditions, time_deadline FROM user_profile WHERE id = %s;", (user_id,))
        result = cur.fetchone()
        result2 =  result+(conn, cur)
        return result2
    except Exception as e:  
        if debug: print("Error fetching one of fitness goal, diet preferences, gender, age, medical conditions and time deadline:", e)
        return tuple('Get into better shape', 'any', 'Female', 18.0, " ", 90 )


# Profile Management: 
def get_user_profile_by_id(user_id: int):
    
# Progress Page: 
def create_daily_entry(user_id: int, activity_level: str) -> bool:
    """Creates new daily entry """


# Perfect:
def get_daily_stats_by_id(user_id: int) -> list[list]:
    """
    Fetch all daily stats for a user, ordered by days_done (ascending).
    Returns 2D list in specified order excluding entry_id, id, and todays_flag.
    Args:
        user_id: The user ID to fetch stats for
        debug: Whether to print debug messages
    Returns:
        List of rows in this order:
        [today_date, progress_condition, activity_level, days_done, 
         days_left, height, weight, diet_history]
        Returns empty list if no results or error occurs
    """
    try:
        conn, cur = connect_db()
        # Query with columns in specified order, excluding todays_flag
        query = """
        SELECT 
            today_date, progress_condition, activity_level, 
            days_done, days_left, height, weight, diet_history
        FROM daily_stats 
        WHERE id = %s
        ORDER BY days_done ASC;
        """
        cur.execute(query, (user_id,))
        rows = cur.fetchall()
        if debug:
            print(f"Fetched {len(rows)} rows for user {user_id}")
            for row in rows:
                print(row)
        # Convert each row tuple to a list
        return [list(row) for row in rows]
    except Exception as e:
        if debug:
            print(f"Error fetching daily stats for user {user_id}: {e}")
        return []  # Return empty list on error (not [[], []])
    finally:
        close_db(conn, cur)
# Chat History Storage
def store_chat_postgres(user_id:int, user_prompt:str, response:str, has_image: bool = False):
    """Fire-and-forget function to store chat in database without waiting"""
    def store_chat_thread():
        try:
            # Add image indicator to the user prompt if an image was attached
            final_user_prompt = user_prompt
            if has_image:
                final_user_prompt = user_prompt + " [Image Attached]"
            conn, cur = connect_db()
            insert_query = """
                INSERT INTO chat_history (id, user_prompt, system_response, time_entered)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            """
            cur.execute(insert_query, (user_id, final_user_prompt, response))
            conn.commit()
            if debug: print("Chat stored successfully.")
        except Exception as e:
            if debug: print(f"Error storing chat: {e}")
        finally:
            close_db(conn, cur)
    # Start the database operation in a separate thread and don't wait for it
    thread = threading.Thread(target=store_chat_thread, daemon=True)
    thread.start()
def get_chat_history_by_date(user_id: int, year: int = None, month: int = None, day: int = None) :
    """
    Retrieves chat history for a specific user and date, ordered by time (oldest first).
    Defaults to today's date if no date parameters are provided.
    
    Args:
        user_id (int): The user ID to fetch chat history for
        year (int): Year (e.g., 2024) - defaults to current year
        month (int): Month (1-12) - defaults to current month
        day (int): Day (1-31) - defaults to current day
        
    Returns:
        List of dictionaries containing chat records with 'time_entered', 'user_prompt', and 'system_response'
    """
    try:
        # Get current date if any parameter is None
        if year is None or month is None or day is None:
            today = datetime.now()
            year = today.year
            month = today.month
            day = today.day
        conn, cur = connect_db()
        # Construct the query to get chat history for a specific date
        query = """
            SELECT time_entered, user_prompt, system_response
            FROM chat_history
            WHERE id = %s
            AND DATE(time_entered) = %s
            ORDER BY time_entered ASC
        """
        target_date = f"{year:04d}-{month:02d}-{day:02d}"
        cur.execute(query, (user_id, target_date))
        results = cur.fetchall()
        chat_history = []
        for record in results:
            chat_history.append({
                'time_entered': record[0],
                'user_prompt': record[1],
                'system_response': record[2]
            })
        return chat_history
    except Exception as e:
        print(f"Error retrieving chat history: {e}")
        return []
    finally:
        close_db(conn, cur)
# Example usage:
# history = get_chat_history_by_date(1, 2024, 12, 15)
# for chat in history:
#     print(f"User: {chat['user_prompt']}")
#     print(f"System: {chat['system_response']}")
#functions ----------------------------------------------------------------------------------------------
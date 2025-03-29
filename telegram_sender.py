import requests
import time
from typing import List, Dict

class TelegramBot:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
    def get_updates(self) -> List[Dict]:
        """Get all updates (messages) from the bot"""
        try:
            response = requests.get(f"{self.base_url}/getUpdates")
            if response.status_code == 200:
                return response.json()['result']
            else:
                print(f"Error getting updates: {response.status_code}")
                return []
        except Exception as e:
            print(f"Error in get_updates: {str(e)}")
            return []
    
    def get_all_chat_ids(self) -> set:
        """Extract unique chat IDs from updates"""
        chat_ids = set()
        updates = self.get_updates()
        
        for update in updates:
            # Get chat_id from messages
            if 'message' in update:
                chat_id = update['message']['chat']['id']
                chat_ids.add(chat_id)
            # Get chat_id from channel posts
            elif 'channel_post' in update:
                chat_id = update['channel_post']['chat']['id']
                chat_ids.add(chat_id)
            
        return chat_ids
    
    def send_message(self, chat_id: int, message: str) -> bool:
        """Send message to a specific chat_id"""
        try:
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'  # Supports HTML formatting
            }
            
            response = requests.post(f"{self.base_url}/sendMessage", json=payload)
            
            if response.status_code == 200:
                print(f"Message sent successfully to chat_id: {chat_id}")
                return True
            else:
                print(f"Failed to send message to chat_id: {chat_id}")
                print(f"Error: {response.text}")
                return False
                
        except Exception as e:
            print(f"Error sending message to {chat_id}: {str(e)}")
            return False
    
    def broadcast_message(self, message: str, delay: int = 1) -> Dict[int, bool]:
        """Send message to all chats"""
        results = {}
        chat_ids = self.get_all_chat_ids()
        
        print(f"Found {len(chat_ids)} chats to message")
        
        for chat_id in chat_ids:
            success = self.send_message(chat_id, message)
            results[chat_id] = success
            
            # Add delay to avoid hitting rate limits
            time.sleep(delay)
        
        return results

def format_job_message(job_details: Dict) -> str:
    """Format job details into a nice message"""
    return f"""
🔍 <b>New Job Match Found!</b>

🏢 <b>Company:</b> {job_details.get('company_name', 'N/A')}
💼 <b>Role:</b> {job_details.get('title', 'N/A')}
🔗 <b>Apply:</b> {job_details.get('apply_url', 'N/A')}

#JobAlert #NewOpportunity
"""

def main():
    # Your bot token from BotFather
    BOT_TOKEN = "your_bot_token_here"
    
    # Initialize bot
    bot = TelegramBot(BOT_TOKEN)
    
    # Example job details
    job_details = {
        'company_name': 'Example Corp',
        'title': 'Senior Software Engineer',
        'apply_url': 'https://linkedin.com/jobs/123456'
    }
    
    # Format message
    message = format_job_message(job_details)
    
    # Send to all chats
    results = bot.broadcast_message(message)
    
    # Print results
    print("\nBroadcast Results:")
    print(f"Total chats: {len(results)}")
    print(f"Successful: {sum(1 for success in results.values() if success)}")
    print(f"Failed: {sum(1 for success in results.values() if not success)}")

if __name__ == "__main__":
    main() 
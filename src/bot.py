import os
import telebot
from telegraph import Telegraph
import requests
import logging
from uuid import uuid4
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
TELEGRAPH_ACCESS_TOKEN = os.getenv('TELEGRAPH_ACCESS_TOKEN')

if not BOT_TOKEN:
    logger.error("BOT_TOKEN is not set in environment variables.")
    raise ValueError("BOT_TOKEN is required.")

# Initialize bot and Telegraph
bot = telebot.TeleBot(BOT_TOKEN)
telegraph = Telegraph(access_token=TELEGRAPH_ACCESS_TOKEN)

# Supported media types
SUPPORTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.mp4']

# Create a Telegraph account if no access token
def create_telegraph_account():
    try:
        response = telegraph.create_account(short_name='MediaBot', author_name='Telegram Media Bot')
        return response['access_token']
    except Exception as e:
        logger.error(f"Failed to create Telegraph account: {e}")
        return None

# Download file from Telegram
def download_file(file_info, file_name):
    file_url = bot.get_file_url(file_info.file_id)
    response = requests.get(file_url)
    if response.status_code == 200:
        with open(file_name, 'wb') as f:
            f.write(response.content)
        return True
    return False

# Upload file to Telegraph
# In handle_media, before upload_to_telegraph
# Download file
if not download_file(file_info, file_name):
    bot.reply_to(message, "Failed to download the file. Try again!")
    return

# Log file details
file_size = os.path.getsize(file_name)
logger.info(f"Processing file: name={os.path.basename(file_name)}, size={file_size} bytes, ext={file_ext}")
if file_size > 5 * 1024 * 1024:  # 5MB limit
    bot.reply_to(message, f"File is too large for Telegraph (max 5MB). Got {file_size / 1024 / 1024:.2f}MB.")
    if os.path.exists(file_name):
        os.remove(file_name)
    return

# Validate file type with magic bytes
import magic
file_mime = magic.from_file(file_name, mime=True)
logger.info(f"File MIME type: {file_mime}")
if file_mime not in ['image/jpeg', 'image/png', 'image/gif', 'video/mp4']:
    bot.reply_to(message, f"Unsupported file type: {file_mime}. Please use JPG, PNG, GIF, or MP4.")
    if os.path.exists(file_name):
        os.remove(file_name)
    return

# Upload to Telegraph
telegraph_url = upload_to_telegraph(file_name)
# Replace upload_to_telegraph function
def upload_to_telegraph(file_path):
    try:
        url = 'https://telegra.ph/upload'
        access_token = os.getenv('TELEGRAPH_ACCESS_TOKEN')
        headers = {'User-Agent': 'MediaToTelegraphBot/1.0'}
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
            logger.info(f"Using Telegraph access token: {access_token[:10]}... (truncated for security)")
        else:
            logger.warning("No Telegraph access token provided; attempting public upload.")
            return None
        # Detect MIME type
        import magic
        mime_type = magic.from_file(file_path, mime=True)
        logger.info(f"Sending file with MIME type: {mime_type}")
        with open(file_path, 'rb') as f:
            file_content = f.read()
        files = {'file': (os.path.basename(file_path), file_content, mime_type)}
        response = requests.post(url, files=files, headers=headers)
        logger.info(f"Request URL: {url}")
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response text: {response.text}")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Parsed response: {data}")
            if isinstance(data, list) and data:
                return data[0].get('src')
            elif isinstance(data, str) and data.startswith('http'):
                return data
            else:
                logger.error(f"Unexpected JSON format: {data}")
                return None
        else:
            logger.error(f"Upload failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Telegraph upload failed: {e}")
        return None
# Start command handler
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Hey, I'm your Media to Telegraph Bot! 😎 Send me an image, video, or document, and I'll give you a Telegraph link to share it. Supported formats: JPG, PNG, GIF, MP4."
    )

# Media handler (photos, videos, documents)
@bot.message_handler(content_types=['photo', 'video', 'document'])
def handle_media(message):
    chat_id = message.chat.id
    try:
        # Determine file type and info
        if message.content_type == 'photo':
            file_info = bot.get_file(message.photo[-1].file_id)  # Get highest resolution
            file_ext = '.jpg'  # Default for photos
        elif message.content_type == 'video':
            file_info = bot.get_file(message.video.file_id)
            file_ext = os.path.splitext(message.video.file_name or '')[1] or '.mp4'
        elif message.content_type == 'document':
            file_info = bot.get_file(message.document.file_id)
            file_ext = os.path.splitext(message.document.file_name or '')[1]
        else:
            bot.reply_to(message, "Unsupported media type. Please send an image, video, or document.")
            return

        # Check if file extension is supported
        if file_ext.lower() not in SUPPORTED_EXTENSIONS:
            bot.reply_to(
                message,
                f"Sorry, {file_ext} is not supported. Please use JPG, PNG, GIF, or MP4."
            )
            return

        # Generate unique file name
        file_name = f"temp_{uuid4().hex}{file_ext}"
        
        # Download file
        if not download_file(file_info, file_name):
            bot.reply_to(message, "Failed to download the file. Try again!")
            return

        # Upload to Telegraph
        telegraph_url = upload_to_telegraph(file_name)
        if telegraph_url:
            full_url = f"https://telegra.ph{telegraph_url}"
            bot.reply_to(
                message,
                f"Here's your Telegraph link: <a href='{full_url}'>View Media</a>",
                parse_mode='HTML'
            )
        else:
            bot.reply_to(message, "Failed to upload to Telegraph. Please try again.")

        # Clean up
        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        logger.error(f"Error processing media: {e}")
        bot.reply_to(message, "Something went wrong! Please try again.")

# Handle unsupported content
@bot.message_handler(content_types=['text', 'audio', 'sticker', 'location', 'contact'])
def handle_unsupported(message):
    bot.reply_to(
        message,
        "Please send an image, video, or document to get a Telegraph link."
    )

# Main function
def main():
    # Check or create Telegraph account
    global telegraph
    if not TELEGRAPH_ACCESS_TOKEN:
        new_token = create_telegraph_account()
        if new_token:
            telegraph = Telegraph(access_token=new_token)
            logger.info("New Telegraph account created.")
        else:
            logger.error("Cannot proceed without a valid Telegraph token.")
            return

    # Start polling
    try:
        logger.info("Starting bot polling...")
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Bot polling failed: {e}")
        bot.stop_polling()

if __name__ == '__main__':
    main()

import os
import requests
import subprocess
import json
import logging
from telegram import Update, ForceReply
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace With Your Telegram Bot Token
TELEGRAM_TOKEN = 'TelegramBotToken'
MEDIA_API_URL = 'https://papernote.online/media-api'
CONTENT_API_URL = 'https://papernote.online/content-api'

# Allowed media types
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
ALLOWED_VIDEO_TYPES = ['video/mp4', 'video/avi']
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB in bytes

# Define states for the content upload conversation
TITLE, AUTHOR, CONTENT = range(3)

# Function to upload media to the API
def upload_media(file_path):
    """Upload media to the API and return the media URL."""
    if not os.path.isfile(file_path):
        logger.error(f"File does not exist: {file_path}")
        raise FileNotFoundError(f"File does not exist: {file_path}")

    command = [
        'curl',
        '-X', 'POST',
        '-F', f'media=@{file_path}',
        MEDIA_API_URL
    ]

    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        response = json.loads(result.stdout.decode())
        media_url = response.get("media_url")
        if media_url:
            return media_url
        else:
            logger.error("media_url not found in the response.")
            raise ValueError("media_url not found in the response.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during curl command: {e.stderr.decode()}")
        raise RuntimeError(f"Error during media upload: {e.stderr.decode()}")


def handle_media(update: Update, context: CallbackContext):
    logger.info("Received a media message.")
    
    if update.message.photo:
        photo_file = update.message.photo[-1].get_file()
        file_path = f"{update.message.chat.id}_photo.jpg"
        photo_file.download(file_path)
        mime_type = 'image/jpeg'
    elif update.message.document:
        doc_file = update.message.document.get_file()
        file_ext = update.message.document.file_name.split('.')[-1].lower()
        mime_type = update.message.document.mime_type
        
        if mime_type in ALLOWED_IMAGE_TYPES:
            file_path = f"{update.message.chat.id}_document.{file_ext}"
        elif mime_type in ALLOWED_VIDEO_TYPES:
            file_path = f"{update.message.chat.id}_video.{file_ext}"
        else:
            update.message.reply_text("Invalid file type. Only images and videos are allowed.")
            return
        
        doc_file.download(file_path)
    else:
        update.message.reply_text("Unsupported media type. Please send an image or video.")
        return

    if not os.path.exists(file_path):
        update.message.reply_text("File download failed. Please try again.")
        return

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        update.message.reply_text("File size exceeds the maximum limit of 20MB.")
        os.remove(file_path)
        return

    logger.info(f"Uploading the media to the API: {file_path}.")
    try:
        media_url = upload_media(file_path)
        update.message.reply_text(f"{media_url}")
    except Exception as e:
        update.message.reply_text(f"There was an error uploading your media: {str(e)}")
    
    os.remove(file_path)

def upload_content_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Please send me the title of the post:",
        reply_markup=ForceReply(selective=True)
    )
    return TITLE

def upload_content_title(update: Update, context: CallbackContext) -> int:
    context.user_data['title'] = update.message.text
    update.message.reply_text(
        "Please send me the author of the post (optional):"
    )
    return AUTHOR

def upload_content_author(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text.strip()
    
    if user_input.lower() == "skip":
        context.user_data['author'] = ''  # Set author to an empty string
    else:
        context.user_data['author'] = user_input
    
    update.message.reply_text(
        "Please send me the HTML content of the post:"
    )
    return CONTENT

def upload_content_content(update: Update, context: CallbackContext) -> int:
    context.user_data['content'] = update.message.text

    title = context.user_data['title']
    author = context.user_data.get('author', '')  # Use blank if not provided
    content = context.user_data['content']

    command = [
        'curl',
        '-X', 'POST',
        '-d', f"title={title}&author={author}&content={content}",
        CONTENT_API_URL
    ]

    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        response = json.loads(result.stdout.decode())
        
        # Extract the post URL from the response
        post_url = response.get("post_url")
        if post_url:
            update.message.reply_text(f"Article Published ❤️‍🔥\n {post_url}")
        else:
            update.message.reply_text("Article uploaded successfully, but no URL was returned.")
    except subprocess.CalledProcessError as e:
        update.message.reply_text(f"Error uploading post: {e.stderr.decode()}")
    
    context.user_data.clear()
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Content upload canceled.")
    context.user_data.clear()  # Clear user data
    return ConversationHandler.END

def upload_content_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Please send me the title of the post:",
        reply_markup=ForceReply(selective=True)
    )
    return TITLE

def upload_content_title(update: Update, context: CallbackContext) -> int:
    context.user_data['title'] = update.message.text
    update.message.reply_text(
        "Please send me the author of the post (optional): (or type 'skip' to skip)"
    )
    return AUTHOR

def upload_content_author(update: Update, context: CallbackContext) -> int:
    user_input = update.message.text.strip()
    
    if user_input.lower() == "skip":
        context.user_data['author'] = ''  # Set author to an empty string
    else:
        context.user_data['author'] = user_input
    
    update.message.reply_text(
        "Please send me the HTML content of the post:"
    )
    return CONTENT

def upload_content_content(update: Update, context: CallbackContext) -> int:
    context.user_data['content'] = update.message.text

    title = context.user_data['title']
    author = context.user_data.get('author', '')  # Use blank if not provided
    content = context.user_data['content']

    command = [
        'curl',
        '-X', 'POST',
        '-d', f"title={title}&author={author}&content={content}",
        CONTENT_API_URL
    ]

    try:
        result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        response = json.loads(result.stdout.decode())
        
        # Extract the post URL from the response
        post_url = response.get("post_url")
        if post_url:
            update.message.reply_text(f"Article Published ❤️‍🔥 \n\n{post_url}")
        else:
            update.message.reply_text("Post uploaded successfully, but no URL was returned.")
    except subprocess.CalledProcessError as e:
        update.message.reply_text(f"Error uploading post: {e.stderr.decode()}")
    
    context.user_data.clear()
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Content upload canceled. 😿")
    context.user_data.clear()
    return ConversationHandler.END

def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🌟 <b>Hello and welcome to the PaperNote Bot!</b> 🌟\n\n"
        "✨ Here, you can effortlessly upload media and text. \n"
        "📘 Use <b>/help</b> to learn how to use me. \n\n"
        "Let’s embark on your creative journey together! 🚀\n\n"
        "<i>This bot uses the PaperNote API ❤️😍 to upload images and texts.</i>",
        parse_mode='HTML'
    )

def help(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🤔 Need help? Just send me your media, or use the <b>/content</b> command to create an article. \n\n"
        "📄 I'm here to assist you every step of the way!",
        parse_mode='HTML'
    )

def love(update: Update, context: CallbackContext):
    update.message.reply_text(
        "PaperNote ❤️😍❤️‍🔥😘",
        parse_mode='HTML'
    )

def dev(update: Update, context: CallbackContext):
    update.message.reply_text(
        "PaperNote ❤️😍❤️‍🔥😘",
        parse_mode='HTML'
    )

def credit(update: Update, context: CallbackContext):
    update.message.reply_text(
        "PaperNote ❤️😍❤️‍🔥😘",
        parse_mode='HTML'
    )

def htmltags(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📜 <b>HTML Formatting Options</b> 📜\n\n"
        "You can enhance your messages using the following HTML tags:\n\n"
        "<strong>Bold:</strong> Use <code>&lt;strong&gt; / &lt;b&gt;</code>\n"
        "<code>&lt;strong&gt;This text is bold&lt;/strong&gt;</code>\n\n"
        "<strong>Italic:</strong> Use <code>&lt;em&gt; / &lt;i&gt;</code>\n"
        "<code>&lt;em&gt;This text is italic&lt;/em&gt;</code>\n\n"
        "<strong>Underline:</strong> Use <code>&lt;u&gt;</code>\n"
        "<code>&lt;u&gt;This text is underlined&lt;/u&gt;</code>\n\n"
        "<strong>Ordered List:</strong> Use <code>&lt;ol&gt;&lt;li&gt;</code>\n"
        "<code>&lt;ol&gt;&lt;li&gt;Item 1&lt;/li&gt;&lt;li&gt;Item 2&lt;/li&gt;&lt;/ol&gt;</code>\n\n"
        "<strong>Bullet List:</strong> Use <code>&lt;ul&gt;&lt;li&gt;</code>\n"
        "<code>&lt;ul&gt;&lt;li&gt;Item 1&lt;/li&gt;&lt;li&gt;Item 2&lt;/li&gt;&lt;/ul&gt;</code>\n\n"
        "<strong>Link:</strong> Use <code>&lt;a href=&quot;URL&quot;&gt;</code>\n"
        "<code>&lt;a href=&quot;https://papernote.online&quot;&gt;Link&lt;/a&gt;</code>\n\n"
        "<strong>Image:</strong> Use <code>&lt;img src=&quot;URL&quot;&gt;</code>\n"
        "<code>&lt;img src=&quot;image.jpg&quot; alt=&quot;description&quot;&gt;</code>\n\n"
        "<strong>Block Quote:</strong> Use <code>&lt;blockquote&gt;</code>\n"
        "<code>&lt;blockquote&gt;This is a quote.&lt;/blockquote&gt;</code>\n\n"
        "<strong>Inline Code:</strong> Use <code>&lt;code&gt;</code>\n"
        "<code>&lt;code&gt;console.log('Hello');&lt;/code&gt;</code>\n\n"
        "<strong>Code Block:</strong> Use <code>&lt;pre&gt;&lt;code&gt;</code>\n"
        "<code>&lt;pre&gt;&lt;code&gt;console.log('Hello');&lt;/code&gt;&lt;/pre&gt;</code>",
        parse_mode='HTML'
    )

def main():
    updater = Updater(TELEGRAM_TOKEN)

    content_handler = ConversationHandler(
        entry_points=[CommandHandler('content', upload_content_start)],
        states={
            TITLE: [MessageHandler(Filters.text & ~Filters.command, upload_content_title)],
            AUTHOR: [MessageHandler(Filters.text & ~Filters.command, upload_content_author)],
            CONTENT: [MessageHandler(Filters.text & ~Filters.command, upload_content_content)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    updater.dispatcher.add_handler(CommandHandler("start", start))
    updater.dispatcher.add_handler(CommandHandler("help", help))
    updater.dispatcher.add_handler(CommandHandler("love", love))
    updater.dispatcher.add_handler(CommandHandler("dev", dev))
    updater.dispatcher.add_handler(CommandHandler("htmltags", htmltags))
    updater.dispatcher.add_handler(MessageHandler(Filters.photo | Filters.document, handle_media))
    updater.dispatcher.add_handler(content_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

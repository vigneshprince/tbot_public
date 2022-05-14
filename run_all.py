from librespot.audio.decoders import AudioQuality
from zspotify import ZSpotify
from track import download_track
from telegram import InputMediaAudio, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    ConversationHandler,
    CallbackQueryHandler,
    CallbackContext,
)
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import sys
import psycopg2
from functools import wraps
from urllib.parse import urlparse

ZSpotify()
ZSpotify.DOWNLOAD_QUALITY = AudioQuality.HIGH

auth_manager = SpotifyClientCredentials()
sp = spotipy.Spotify(auth_manager=auth_manager)

arrow = "\U000027A1"

TRACK, ALBUM, ALBUM_CALLBACK, TRACK_CALLBACK, GD_FILE, GD_FOLDER, GD_FILE_CALLBACK, GD_FOLDER_CALLBACK = range(
    8)

GD_FOLDER_ID = '0AM6erVIeZBcOUk9PVA'

SCOPES = ['https://www.googleapis.com/auth/drive']
creds = None
if os.path.exists('gdrive_cred/token.pickle'):
    with open('gdrive_cred/token.pickle', 'rb') as token:
        creds = pickle.load(token)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'gdrive_cred/credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open('gdrive_cred/token.pickle', 'wb') as token:
        pickle.dump(creds, token)

service = build('drive', 'v3', credentials=creds)

moviedata = {}
songdata = {}
cancelFlag = {}
moviestack = []
main_link = "https://x.x.workers.dev/0:/"


try:
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
except:
    result = urlparse(
        "postgres://xswpoujzkyzlyv:85823cf30913cf0843ff727567618a51a3b72b32915f9640561c19b61f898645@ec2-34-195-69-118.compute-1.amazonaws.com:5432/df6ocpna6ks7um")
    username = result.username
    password = result.password
    database = result.path[1:]
    hostname = result.hostname
    port = result.port
    conn = psycopg2.connect(
        database=database,
        user=username,
        password=password,
        host=hostname,
        port=port
    )
cur = conn.cursor()
cur.execute(""" select * from telegram_users""")
access_list = [item[0] for item in cur.fetchall()]


def add(update, context):
    global access_list
    global cur, conn
    if(update.effective_user.username == 'vigneshprince75'):
        try:
            cur.execute(
                """ INSERT INTO telegram_users VALUES ('{}')""".format(context.args[0]))
            conn.commit()
        except:
            conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            cur = conn.cursor()
            cur.execute(
                """ INSERT INTO telegram_users VALUES ('{}')""".format(context.args[0]))
            conn.commit()
        access_list.append(context.args[0])
        update.message.reply_text('Added  '+context.args[0])
    else:
        update.message.reply_text('Only Admin can add users')


def restricted(func):
    @wraps(func)
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.username
        if user_id not in access_list:
            update.message.reply_text("access denied ")
            return
        return func(update, context, *args, **kwargs)
    return wrapped


def getbyItr(arr, itr):
    for a in arr:
        if a['itr'] == itr:
            return a
    return None


def renamer(text):
    return(text.replace(' ', '%20'))


def humansize(nbytes):
    nbytes = int(nbytes)
    i = 0
    while nbytes >= 1024 and i < len(['B', 'KB', 'MB', 'GB', 'TB', 'PB'])-1:
        nbytes /= 1024.
        i += 1
    f = ('%.2f' % nbytes).rstrip('0').rstrip('.')
    return '%s %s' % (f, ['B', 'KB', 'MB', 'GB', 'TB', 'PB'][i])


def build_menu(buttons, n_cols, header_buttons=None, footer_buttons=None):
    menu = [buttons[i:i + n_cols] for i in range(0, len(buttons), n_cols)]
    if header_buttons:
        menu.insert(0, header_buttons)
    if footer_buttons:
        menu.append(footer_buttons)
    return menu


@restricted
def album(update: Update, context: CallbackContext):
    update.message.reply_text('Enter album name')
    return ALBUM


@restricted
def track(update: Update, context: CallbackContext):
    temp = update.message.reply_text('Enter track name')
    return TRACK


@restricted
def gd_file(update: Update, context: CallbackContext):

    temp = update.message.reply_text('Enter movie name')
    return GD_FILE


@restricted
def gd_folder(update: Update, context: CallbackContext):

    temp = update.message.reply_text('Enter folder name')
    return GD_FOLDER


def track_name(update: Update, context: CallbackContext):
    global songdata

    results = sp.search(q='track:' + update.message.text, type='track')
    results = results['tracks']['items']

    songdata[update.effective_user.id] = [[{'name': f['name'], 'artist':','.join(
        [d['name'] for d in f['artists']]), 'id':f['id'], 'itr':i} for i, f in enumerate(results)]]
    menu = list_gen('songs', 0, update.effective_user.id)

    update.message.reply_text(
        'Select Track',
        reply_markup=InlineKeyboardMarkup(menu)
    )
    return TRACK_CALLBACK


def album_name(update: Update, context: CallbackContext):

    global songdata
    results = sp.search(q='album:' + update.message.text, type='album')

    results = results['albums']['items']
    songdata[update.effective_user.id] = [[{'name': f['name'], 'artist':','.join(
        [d['name'] for d in f['artists']]), 'id':f['id'], 'itr':i} for i, f in enumerate(results)]]
    menu = list_gen('songs', 0, update.effective_user.id)
    update.message.reply_text(
        'Select Album',
        reply_markup=InlineKeyboardMarkup(menu)
    )
    return ALBUM_CALLBACK


def track_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    global cancelFlag
    if('next' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('songs', start, update.effective_user.id)
        query.edit_message_text(
            'Select Track',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return TRACK_CALLBACK
    elif('back' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('songs', start, update.effective_user.id)
        query.edit_message_text(
            'Select Track',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return TRACK_CALLBACK
    elif('uplevel' in query.data):
        songdata[update.effective_user.id].pop()
        menu = list_gen('songs', 0, update.effective_user.id)
        query.edit_message_text(
            'Select Album',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return ALBUM_CALLBACK
    elif('copyfolder' in query.data):
        query.bot.send_message(query.message.chat.id,
                               '/cancel to cancel transfer')
        for item in songdata[update.effective_user.id][-1]:
            if(update.effective_user.id in cancelFlag and cancelFlag[update.effective_user.id] == True):
                cancelFlag[update.effective_user.id] = False
                break
            else:
                reply = query.bot.send_message(
                    query.message.chat.id, f"Downloading {item['name']}")
                fname = download_track('single', item['id'])
                query.bot.editMessageText(
                    f"Uploading {item['name']}", chat_id=query.message.chat.id, message_id=reply.message_id)
                query.bot.send_audio(query.message.chat.id,
                                     audio=open(fname, 'rb'))
                query.bot.editMessageText(
                    'Done', chat_id=query.message.chat.id, message_id=reply.message_id)
                os.remove(fname)

    else:
        reply = query.bot.send_message(query.message.chat.id, 'Downloading')
        fname = download_track('single', query.data)
        query.bot.editMessageText(
            'Uploading', chat_id=query.message.chat.id, message_id=reply.message_id)
        query.bot.send_audio(query.message.chat.id, audio=open(fname, 'rb'))
        query.bot.editMessageText(
            'Done', chat_id=query.message.chat.id, message_id=reply.message_id)
        os.remove(fname)


def album_callback(update: Update, context: CallbackContext):

    global songdata

    query = update.callback_query
    query.answer()

    if('next' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('songs', start, update.effective_user.id)
        query.edit_message_text(
            'Select Track',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return ALBUM_CALLBACK
    elif('back' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('songs', start, update.effective_user.id)
        query.edit_message_text(
            'Select Track',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return ALBUM_CALLBACK
    else:
        results = sp.album_tracks(query.data, limit=50, offset=0)
        results = results['items']

        songdata[update.effective_user.id].append([{'name': f['name'], 'artist':','.join(
            [d['name'] for d in f['artists']]), 'id':f['id'], 'itr':i} for i, f in enumerate(results)])

        menu = list_gen('songs', 0, update.effective_user.id, True)
        query.edit_message_text(
            'Select Track',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return TRACK_CALLBACK


def gd_file_transfer(mdetail, call, parent=False, parent_id='',href=True):

    msg = "Transferring .."+mdetail['name']
    reply = call.bot.send_message(call.message.chat.id, msg)
    newfile = {'name': mdetail['name'], 'parents': [
        parent_id if parent else GD_FOLDER_ID]}
    try:
        service.files().copy(
            fileId=mdetail['id'], supportsAllDrives=True, body=newfile).execute()
        if href:
            link = "<a href='{}'>{}</a>".format(main_link +
                                                renamer(mdetail['name']), mdetail['name'])
            msg = call.bot.editMessageText(text=link, chat_id=call.message.chat.id,
                                       message_id=reply.message_id, parse_mode='html')
        else:
            msg = call.bot.editMessageText(text=mdetail['name'], chat_id=call.message.chat.id,
                                       message_id=reply.message_id)

        

    except:
        call.bot.editMessageText(f"Failed {mdetail['name']} !! Try another file", chat_id=call.message.chat.id,
                                 message_id=reply.message_id)

    return


def gd_folder_transfer(data, call, foldername, uid):
    global cancelFlag
    file_metadata = {
        'name': foldername,
        'parents': [GD_FOLDER_ID],
        'mimeType': 'application/vnd.google-apps.folder'
    }

    folder_info = service.files().create(
        body=file_metadata, supportsAllDrives=True, fields='id').execute()
    call.bot.send_message(call.message.chat.id, '/cancel to cancel transfer')

    threads=[]
    for i in data:
        if('folder' not in i['mimeType']):
            if(uid in cancelFlag and cancelFlag[uid] == True):
                cancelFlag[uid] = False
                break
            else:
                gd_file_transfer(i, call, True, folder_info['id'],False)

    return


def getFolderfromID(query, curr_folder, user):
    q = f"'{curr_folder['id']}' in parents and trashed=false"

    q = service.files().list(
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        pageSize=1000,
        fields="files/name,files/id,files/parents,files/mimeType,files/size",
        q=q
    ).execute()
    global moviedata

    if(len(q['files']) > 0):
        temp = []
        for i, f in enumerate(q['files']):
            if('folder' not in f['mimeType']):
                temp.append({'itr': i,
                            'parent': f['parents'][0],
                             'name':humansize(f['size']) + '-'+f['name'] if 'folder' not in f['mimeType'] else f['name'],
                             'id': f['id'],
                             'size': f['size'],
                             'mimeType': f['mimeType']})
            else:
                temp.append({'itr': i,
                            'parent': f['parents'][0],
                             'name': arrow+' '+f['name'] if 'folder' in f['mimeType'] else f['name'],
                             'id': f['id'],
                             'mimeType': f['mimeType']})

        moviedata[user].append(temp)
        menu = list_gen('gd', 0, user, True, curr_folder['name'])
        return menu
    else:
        return []


def gd_file_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    menu = []
    if('next' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('gd', start, update.effective_user.id)
    elif('back' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('gd', start, update.effective_user.id)
    else:
        gd_file_transfer(
            getbyItr(moviedata[update.effective_user.id][-1], int(query.data)), query)
    if menu:
        query.edit_message_text(
            'Select Movie',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return GD_FILE_CALLBACK


def gd_folder_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    menu = []
    if('next' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('gd', start, update.effective_user.id)
    elif('back' in query.data):
        start = int(query.data.split(';')[1])
        menu = list_gen('gd', start, update.effective_user.id)
    elif('uplevel' in query.data):
        moviedata[update.effective_user.id].pop()
        uplevel_flag = True if len(
            moviedata[update.effective_user.id]) > 1 else False
        menu = list_gen('gd', 0, update.effective_user.id, uplevel_flag)
    elif('copyfolder' in query.data):
        curr_folder_name = query.data.split(';')[1]
        gd_folder_transfer(moviedata[update.effective_user.id]
                           [-1], query, curr_folder_name, update.effective_user.id)
    else:
        mdetail = getbyItr(
            moviedata[update.effective_user.id][-1], int(query.data))
        print(mdetail)
        if('folder' in mdetail['mimeType']):
            menu = getFolderfromID(
                query, mdetail, update.effective_user.id)
        else:
            gd_file_transfer(mdetail, query)
    if menu:
        query.edit_message_text(
            'Select Folder/File',
            reply_markup=InlineKeyboardMarkup(menu)
        )
        return GD_FOLDER_CALLBACK


def list_gen(mode, start, userid, uplevel=False, foldername=''):

    if(mode == 'gd'):
        curr_data = moviedata[userid][-1]
        last_index = len(curr_data)-1
        end = min(start+9, last_index)
        limit_data = curr_data[start:end+1]
        list_data = list(
            map(lambda x: [x['name'], str(x['itr'])], limit_data))

    if(mode == 'songs'):
        curr_data = songdata[userid][-1]
        last_index = len(curr_data)-1
        end = min(start+9, last_index)
        limit_data = curr_data[start:end+1]
        list_data = list(
            map(lambda x: [x['name']+' - '+x['artist'], str(x['id'])], limit_data))
    button_list = []
    if list_data:
        for i in list_data:
            button_list.append(InlineKeyboardButton(i[0], callback_data=i[1]))
            menu = build_menu(button_list, n_cols=1)
        next_flag = True if(last_index > end) else False
        navigation = []
        if(next_flag):
            navigation.append(InlineKeyboardButton(
                'Next', callback_data='next;'+str(end+1)))
        if(end > 9):
            navigation.append(InlineKeyboardButton(
                'Back', callback_data='back;'+str(start-10)))
        if(uplevel):
            navigation.append(InlineKeyboardButton(
                'Up one Level', callback_data='uplevel'))
            navigation.append(InlineKeyboardButton(
                'Copy All Files', callback_data=f'copyfolder;{foldername[2:50]}'))
        if navigation:
            menu.append(navigation)
        return menu
    return []


def gd_file_query(update: Update, context: CallbackContext):

    q = "mimeType contains 'video/' and trashed=false and fullText contains '{}'".format(
        update.message.text)

    query = service.files().list(
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        pageSize=1000,
        fields="files/name,files/id,files/parents,files/mimeType,files/size",
        q=q
    ).execute()
    global moviedata

    if(len(query['files']) > 0):
        sorted_query = sorted(
            query['files'], key=lambda x: int(x['size']), reverse=True)
        moviedata[update.effective_user.id] = [[{'itr': i, 'parent': f['parents'][0], 'name':humansize(f['size']) + '- '+f['name'], 'id':f['id'], 'mimeType':f['mimeType']} for i, f in enumerate(sorted_query)]]

        menu = list_gen('gd', 0, update.effective_user.id)
        update.message.reply_text(
            'Select Movie',
            reply_markup=InlineKeyboardMarkup(menu)
        )
    else:
        update.message.reply_text("Movie Not Found")
    return GD_FILE_CALLBACK


def gd_folder_query(update: Update, context: CallbackContext):

    q = "mimeType='application/vnd.google-apps.folder' and trashed=false and fullText contains '{}'".format(
        update.message.text)

    query = service.files().list(
        corpora="allDrives",
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        pageSize=1000,
        fields="files/name,files/id,files/parents,files/mimeType",
        q=q
    ).execute()
    global moviedata
    if(len(query['files']) > 0):
        moviedata[update.effective_user.id] = [[{'itr': i, 'parent': f['parents'][0], 'name':arrow +
                                                 ' '+f['name'], 'id':f['id'], 'mimeType':f['mimeType']} for i, f in enumerate(query['files'])]]

        menu = list_gen('gd', 0, update.effective_user.id)
        update.message.reply_text(
            'Select Movie',
            reply_markup=InlineKeyboardMarkup(menu)
        )
    else:
        update.message.reply_text("Movie Not Found")
    return GD_FOLDER_CALLBACK


@restricted
def start(update: Update, context: CallbackContext):

    reply_keyboard = [['/gd_file', '/gd_folder'], ['/album', '/track']]
    update.message.reply_text(
        'Select an option to start',
        reply_markup=ReplyKeyboardMarkup(
            reply_keyboard, resize_keyboard=True),
    )


@restricted
def cancel(update: Update, context: CallbackContext):
    global cancelFlag
    cancelFlag[update.effective_user.id] = True


def main() -> None:
    updater = Updater("telegram bot code")
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('album', album), CommandHandler(
            'track', track), CommandHandler(
            'gd_file', gd_file), CommandHandler(
            'gd_folder', gd_folder)],
        states={
            TRACK: [MessageHandler(Filters.text, track_name)],
            ALBUM: [MessageHandler(Filters.text, album_name)],
            ALBUM_CALLBACK: [CallbackQueryHandler(album_callback)],
            TRACK_CALLBACK: [CallbackQueryHandler(track_callback, run_async=True)],
            GD_FILE: [MessageHandler(Filters.text, gd_file_query)],
            GD_FOLDER: [MessageHandler(Filters.text, gd_folder_query)],
            GD_FILE_CALLBACK: [CallbackQueryHandler(gd_file_callback)],
            GD_FOLDER_CALLBACK: [CallbackQueryHandler(gd_folder_callback, run_async=True)],
        },
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )

    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("cancel", cancel))
    dispatcher.add_handler(CommandHandler("add", add))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()

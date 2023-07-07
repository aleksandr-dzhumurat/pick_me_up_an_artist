"""
----------------------------
Visualization app on Streamlit
----------------------------
"""
import logging
import random
from typing import Dict

import requests
import streamlit as st

# from utils import logger
logger = logging.getLogger('my_logger')

logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

def do_action(action_type: str, item_id: int, tag: str, user_token: str, user_name: str):
    if action_type in ('like', 'dislike'):
        myobj = {'item_id': item_id, 'action_type': action_type, 'user_token': user_token, 'user_name': user_name, 'item_tag': tag}
        requests.post('http://pickupartist_container:8090/action', json = myobj)

def request_random_artist_json(num_retries: int = 10) -> Dict:
    res = {}
    for i in range(num_retries):
        content_url = 'http://pickupartist_container:8090/random'
        user_data = {'user_name': st.session_state['user_name']}
        random_content = requests.post(content_url, json = user_data).json()
        artist_id = random_content['item_id']
        artist_tag = random_content['item_tag']
        logger.info('random artist: %d', artist_id)
        url = f'http://pickupartist_container:8090/items/{artist_id}'
        try:
            res = requests.get(url).json()
            res.update({'tag': artist_tag})
            return res
        except requests.exceptions.ConnectionError as e:
            logger.error('%s\n%s', url, e)
            #  time.sleep(1)
        except requests.exceptions.JSONDecodeError as e:
            logger.error('%s\n%s', url, e)
    return res

def main():
    app_formal_name = "Swipe an artist"
    st.set_page_config(
        layout="wide", page_title=app_formal_name,
    )

    title_element = st.empty()
    title_element.title("Swipe an artist!")

    if not 'session_started' in st.session_state.keys():
        auth_button = st.button('Start session 🚀')
    if 'session_started' not in st.session_state.keys() and auth_button:
        user_name = requests.get('https://names.drycodes.com/1').json()[0]
        auth_url = 'http://pickupartist_container:8090/auth'
        user_token = requests.post(auth_url, json = {'user_name': user_name}).json()['Bearer']
        st.session_state['session_started'] = True
        st.session_state['user_token'] = user_token
        st.session_state['user_name'] = user_name
        st.session_state['content_count'] = 0
        logger.info('Session start for %s', user_name)
    
    if 'session_started' in st.session_state.keys() and st.session_state['session_started'] is True:
        if st.session_state['content_count'] == 5:
            user_data = {'user_name': st.session_state['user_name']}
            rec_url = 'http://pickupartist_container:8090/recommend'
            res = requests.post(rec_url, json = user_data).json()['rec']
            st.write('We recommend you based on your tags: %s' % res['tags'])
            gallery = res['gallery']
            st.write(gallery['exhibition_link'])
            print(gallery['gallery_img'])
            st.image(gallery['gallery_img'], caption=gallery['name'])
        else:
            st.session_state['content_count'] = st.session_state['content_count'] + 1
            user_name = st.session_state['user_name']
            user_token = st.session_state['user_token']  # exists for sure because session is already started
            random_artist = request_random_artist_json()
            artist_id = random_artist['item']['artist_id']
            col1, col2, col3 = st.columns([1, 2, 1], gap='large')
            with col1:
                like_button = st.button('🤩')
            with col2:
                st.write('%d of 10' % st.session_state['content_count'])
            with col3:
                dislike_button = st.button('🥴')
            if like_button:
                do_action('like', artist_id, random_artist['tag'], user_token, user_name)
            if dislike_button:
                do_action('dislike', artist_id, random_artist['tag'], user_token, user_name)

            st.image(random_artist['item']['artworks'], caption=random_artist['item']['artwork_name'])
            st.write(f"""[{random_artist['item']['artist_name']}]({random_artist['item']['artist_url']}), {random_artist['item']['field']}, {random_artist['item']['artist_movement']}""")

if __name__ == '__main__':
    main()
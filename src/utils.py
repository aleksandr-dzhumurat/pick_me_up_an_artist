import json
import logging
import os
import random
import string
from typing import Optional, Dict, Tuple, List

import pandas as pd
import numpy as np
import yaml
from pymongo import MongoClient
from bson.objectid import ObjectId
from sklearn.metrics.pairwise import cosine_similarity

from src.prepare_data import load_embedder

MONGO_HOST = os.environ['MONGO_HOST']
logger = logging.getLogger('my_logger')
logging.basicConfig(format='%(asctime)s: %(message)s', level=logging.INFO)

embedder = load_embedder()


def load_config() -> dict:
    config_path = os.getenv("CONFIG_PATH", "config.yml")
    with open(config_path, "r") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    return config


config = load_config()

def artifact_path(artifact_name: str):
    artifacts_dirname  = f"{config['data_version']}_service_data"
    return os.path.join(config['root_data_dir'], artifacts_dirname, artifact_name)

def user_tags_ranking(user_actions: Dict, all_tags_df: pd.DataFrame):
    tags_df = all_tags_df.copy()
    if len(user_actions) > 0:
        user_negative_tags = pd.json_normalize([i for i in user_actions if i['action']=='dislike'])
        if user_negative_tags.shape[0] > 0:
            user_negative_tags = user_negative_tags['content_tag'].value_counts().to_frame(name='cnt').reset_index()
            user_negative_tags.columns = ['content_tag', 'cnt']
        user_positive_tags = pd.json_normalize([i for i in user_actions if i['action']=='like'])
        if user_positive_tags.shape[0] > 0:
            user_positive_tags = user_positive_tags['content_tag'].value_counts().to_frame(name='cnt').reset_index()
            user_positive_tags.columns = ['content_tag', 'cnt']
        if user_negative_tags.shape[0] > 0:  # drop disliked tags
            tags_df = (
                tags_df
                .merge(user_negative_tags, how='left', left_on='tag', right_on='content_tag',suffixes=('','_neg'))
                .query('cnt_neg.isnull()')
                [['tag', 'cnt']]
            )
        if user_positive_tags.shape[0] > 0:
            tags_df = (
                tags_df
                .merge(user_positive_tags, how='left', left_on='tag', right_on='content_tag',suffixes=('','_pos'))
                .sort_values('cnt_pos', ascending=False)
                [['tag', 'cnt', 'cnt_pos']]
            ).head(3)  # add
            print(tags_df.head(5))
    return tags_df


class ContentDB:
    def __init__(self):
        self.df = None  # type: Optional[pd.DataFrame]
        self.tags_df = None  # type: Optional[pd.DataFrame]
        
    def init_db(self):
        self.df = pd.read_csv(artifact_path('content_db.csv.gz'), compression='gzip')
        print('Num artists %d' % self.df.shape[0])
        self.tags_df = pd.read_csv(artifact_path('tags_db.csv.gz'), compression='gzip').query('cnt > 1')
        excluded_tags = ['art']
        self.tags_df.drop(self.tags_df[self.tags_df['tag'].isin(excluded_tags)].index, inplace=True)
        print('Num tags %d' % self.tags_df.shape[0])
    
    def get_content(self, content_id: int) -> Dict:
        content_info = self.df.iloc[content_id].to_dict()
        res = {}
        res.update({'artist_movement': content_info['artist_movement']})
        res.update({'field': content_info['artist_field']})
        random_artwork = np.random.choice(json.loads(content_info['artworks']))
        artwork_name = json.dumps(random_artwork.split('/')[-1].split('.')[0].replace('-', ' '))
        res.update({'artworks': random_artwork, 'artwork_name': artwork_name})
        res.update({'artist_id': content_id, 'artist_name': content_info['artist_name'], 'artist_url': content_info['artist_url']})
        for key in res.keys():
            if not isinstance(res[key], str):
                if np.isnan(res[key]):
                    res[key] = 'Empty'
        return res
    
    def get_random_content(self, user_actions: List[Dict[str, str]], eps: float = 0.3) -> dict:
        print(user_actions)
        # bandit logic
        if np.random.random() < eps or len(user_actions) == 0:
            random_tag = np.random.choice(self.tags_df['tag'])
        else:
            random_tag = np.random.choice(user_tags_ranking(user_actions, self.tags_df)['tag'].values)
        logger.info('random tag: %s', random_tag)
        res = int(np.random.choice(
            self.df[
                self.df['art_tags']  # artist_movement
                .apply(lambda x: random_tag in x.lower() if isinstance(x, str) else False)
            ].index
        ))
        return {'item_id': res, 'item_tag': random_tag}

class UserDB:
    def __init__(self):
        self.mongo = None
    
    def init_db(self):
        self.mongo = MongoClient(f'mongodb://{MONGO_HOST}:27017/')
        self.user_actions = self.mongo['artswipe_db']['user_actions']
    
    def get_user_actions(self, user_name: str) -> Tuple[str, List[Dict]]:
        # TODO: add cache
        user_activity = self.user_actions.find_one({'name': user_name})
        user_actions = []
        if user_activity is None:
            return None, None
        else:
            return str(user_activity['_id']), user_activity['actions']

    def create_user(self, user_name: str) -> str:
        user_id, user_actions = self.get_user_actions(user_name)
        if user_id is None:
            user_id = (
                self.user_actions
                .insert_one({'name': user_name, 'actions': []})
                .inserted_id
            )
        else:
            logger.info('User already exists')
        return str(user_id)

    def push_action(self, user_id: str, content_id: str, content_tag: str, action_type: str) -> str:
        action = {'content_id': content_id, 'content_tag': content_tag,'action': action_type}
        self.user_actions.update_one({'_id': ObjectId(user_id)}, {'$push': {'actions': action}})
        return True


class GalleryDB:
    def __init__(self):
        self.df = None  # type: Optional[pd.DataFrame]
        self.embedder = embedder
    
    def validate_galleries(self):
        df_filter = self.df['exhibition_description'].isna()
        self.df.drop(self.df[df_filter].index, inplace=True)

        df_filter = self.df['gallery_imgs'].isna()
        self.df.drop(self.df[df_filter].index, inplace=True)

        df_filter = self.df['gallery_imgs'].apply(lambda x: len(x) == 0)
        self.df.drop(self.df[df_filter].index, inplace=True)
        
    def init_db(self):
        self.df = pd.read_csv(artifact_path('exhibitions_db.csv.gz'), compression='gzip')
        print('Num gallerys %d' % self.df.shape[0])
        self.validate_galleries()
        print('Num gallerys after filtering %d' % self.df.shape[0])
        # vectorizing model
        embeds_path = artifact_path('embeds.npy')
        if not os.path.exists(embeds_path):
            logger.info('Evaluating_embeds')
            raw_corpus = self.df['exhibition_description'].values
            index = self.embedder.encode(raw_corpus, show_progress_bar=True)
            self.index = np.array([embedding for embedding in index]).astype("float32")
            np.save(embeds_path, self.index)
        else:
            logger.info('Loading embeds from %s', embeds_path)
            self.index = np.load(embeds_path)
        logger.info('Embeds created %d', self.index.shape[0])
    
    def get_content(self, content_id: Optional[int]) -> Dict:
        if content_id is None:
            content_id = np.random.choice(self.df.index)
        content_info = self.df.iloc[content_id].to_dict()
        res = {}
        res.update({'name': content_info['galery_name']})
        res.update({'exhibition_link': content_info['exhibition_link']})
        imgs_raw = content_info['gallery_imgs']
        logger.info('id: %d, type: %s, IMG: %s', content_id, type(imgs_raw), imgs_raw)
        # imgs = json.loads(imgs_raw)
        imgs = eval(imgs_raw)  # TODO: find a bug with JSON
        gallery_img = ''
        if len(imgs) > 0:
            gallery_img = np.random.choice(imgs)
        res.update({'exhibition_link': content_info['exhibition_link'], 'gallery_img': gallery_img})
        if not isinstance(content_info['artist_link'], str):
            artist_link = content_info['exhibition_link']
        else:
            artist_link = content_info['artist_link']
        res.update({'artist_link': artist_link})
        print('RES', res)
        return res
    
    def recommend(self, user_actions: List[Dict[str, str]]) -> dict:
        user_positive_tags = [i['content_tag'] for i in user_actions if i['action']=='like']
        user_pref = ''
        if len(user_positive_tags) > 0:
            user_pref = ' '.join(user_positive_tags)
            query_embed = self.embedder.encode(user_pref).reshape(1, -1)
            sim = cosine_similarity(query_embed, self.index)[0]
            most_similar_id = np.argsort(-sim)[0]
            top_gallery = self.get_content(most_similar_id)
        else:
            logger.info('random recommendation')
            top_gallery = self.get_content(None)
        return {'gallery': top_gallery, 'tags': user_pref}

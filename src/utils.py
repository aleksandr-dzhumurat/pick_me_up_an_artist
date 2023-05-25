import json
import random
import string
from typing import Optional, Dict, Tuple, List

import pandas as pd
import numpy as np
from pymongo import MongoClient
from bson.objectid import ObjectId


class ContentDB:
    def __init__(self):
        self.df = None  # type: Optional[pd.DataFrame]
        self.tags_df = None  # type: Optional[pd.DataFrame]
        
    def init_db(self):
        df = pd.read_csv('/srv/data/content_db_v01.csv')
        print('Num artists %d' % df.shape[0])
        self.df = df
        self.tags_df = pd.read_csv('/srv/data/content_tags_v01.csv')
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
    
    def get_random_content(self, user_actions: List[Dict[str, str]]) -> dict:
        if len(user_actions) > 0:
            user_negative_tags = pd.json_normalize([i for i in user_actions if i['action']=='dislike'])
            if user_negative_tags.shape[0] > 0:
                user_negative_tags = user_negative_tags.content_tag.value_counts().to_frame(name='cnt').reset_index()
                user_negative_tags.columns = ['content_tag', 'cnt']
            user_positive_tags = pd.json_normalize([i for i in user_actions if i['action']=='like'])
            if user_positive_tags.shape[0] > 0:
                user_positive_tags = user_positive_tags.content_tag.value_counts().to_frame(name='cnt').reset_index()
                user_positive_tags.columns = ['content_tag', 'cnt']
            # print(user_positive_tags)
            # drop disliked tags
            tags_df = self.tags_df
            if user_negative_tags.shape[0] > 0:
                print('Positive filtered')
                print(user_negative_tags)
                tags_df = (
                    tags_df
                    .merge(user_negative_tags, how='left', left_on='tag', right_on='content_tag',suffixes=('','_neg'))
                    .query('cnt_neg.isnull()')
                    [['tag', 'cnt']]
                )
            if user_positive_tags.shape[0] > 0:
                print('Negative filtered')
                print(user_positive_tags)
                #print(tags_df.merge(user_positive_tags, how='left', left_on='tag', right_on='content_tag',suffixes=('','_pos')))
                #print(tags_df.merge(user_positive_tags, how='left', left_on='tag', right_on='content_tag',suffixes=('','_pos')))
                tags_df = (
                    tags_df
                    .merge(user_positive_tags, how='left', left_on='tag', right_on='content_tag',suffixes=('','_pos'))
                    .sort_values('cnt_pos', ascending=False)
                    [['tag', 'cnt']]
                )
        else:
            tags_df = self.tags_df
        random_tag = np.random.choice(tags_df['tag'])
        res = int(np.random.choice(
            self.df[
                self.df['artist_movement']
                .apply(lambda x: random_tag in x.lower() if isinstance(x, str) else False)
            ].index
        ))
        return {'item_id': res, 'item_tag': random_tag}

class UserDB:
    def __init__(self):
        self.mongo = None
    
    def init_db(self):
        self.mongo = MongoClient("mongodb://artinder_mongo:27017/")
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

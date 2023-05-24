import json
import random
import string
from typing import Optional, Dict

import pandas as pd
import numpy as np
from pymongo import MongoClient
from bson.objectid import ObjectId


class ContentDB:
    def __init__(self):
        self.df = None  # type: Optional[pd.DataFrame]
        
    def init_db(self):
        df = pd.read_csv('/srv/data/content_db_v01.csv')
        print('Num rows %d' % df.shape[0])

        self.df = df
    
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
    
    def get_random_content_id(self) -> int:
        res = int(np.random.choice(self.df.index))
        return res

class UserDB:
    def __init__(self):
        self.mongo = None
    
    def init_db(self):
        self.mongo = MongoClient("mongodb://artinder_mongo:27017/")
        self.user_actions = self.mongo['artswipe_db']['user_actions']
    
    def create_user(self, user_name: str) -> str:
        created_user_id = (
            self.user_actions
            .insert_one({'name': user_name, 'actions': []})
            .inserted_id
        )
        return str(created_user_id)

    def push_action(self, user_id: str, content_id: str, action_type: str) -> str:
        action = {'content_id': content_id, 'action': action_type}
        self.user_actions.update_one({'_id': ObjectId(user_id)}, {'$push': {'actions': action}})
        return True

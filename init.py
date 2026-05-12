from tqdm import tqdm
import json
from string import Template
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from init_code.init_compound_embedding_data import init_compound_embedding_data

if __name__ == "__main__":
    # init_compound_embedding_data()
    
    print("init finished")
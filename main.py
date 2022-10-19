import os
import urllib.request as request
import requests
import pandas as pd
import datetime
import argparse
import yaml

from addict import Dict
from tqdm import tqdm



# 代理设置
proxies = {
    'https': 'https://127.0.0.1:7890',  # 查找到你的vpn在本机使用的https代理端口
    'http': 'http://127.0.0.1:7890',  # 查找到vpn在本机使用的http代理端口
}

opener = request.build_opener(request.ProxyHandler(proxies))
request.install_opener(opener)

def read_yaml(fpath="./configs/sample.yaml"):
    with open(fpath, mode="r") as file:
        yml = yaml.load(file, Loader=yaml.Loader)
        return Dict(yml)

# 登录
def log_in(config_path):

    cfg = read_yaml(config_path)


    # https://www.reddit.com/prefs/apps 从这个网站获取
    CLIENT_ID = cfg.CLIENT_ID
    SECRET_TOKEN = cfg.SECRET_TOKEN

    # note that CLIENT_ID refers to 'personal use script' and SECRET_TOKEN to 'token'
    auth = requests.auth.HTTPBasicAuth(CLIENT_ID, SECRET_TOKEN)

    # here we pass our login method (password), username, and password
    data = {'grant_type': 'password',
            'username': cfg.username,
            'password': cfg.password}

    # setup our header info, which gives reddit a brief description of our app
    headers = {'User-Agent': 'MyBot/0.0.1'}

    # send our request for an OAuth token
    res = requests.post('https://www.reddit.com/api/v1/access_token',
                        auth=auth, data=data, headers=headers, proxies=proxies)

    TOKEN = res.json()['access_token']
    # add authorization to our headers dictionary
    headers = {**headers, **{'Authorization': f"bearer {TOKEN}"}}

    # while the token is valid (~2 hours) we just add headers=headers to our requests
    return headers

def article_spider(headers, url='https://oauth.reddit.com/r/depression/', article_num=2000, after=None):
    count = 0
    params = {'limit': '64'}
    if after is not None:
        params['after'] = after
    keys = ['id', 'created_utc', 'title', 'selftext', 'author_fullname', 'author', 'permalink', 'upvote_ratio', 'score',
            'num_comments']
    data = {key: [] for key in keys}
    with tqdm(total=article_num) as bar:
        while count < article_num:
            res = requests.get(url, headers=headers, proxies=proxies, params=params)
            res_json = res.json()
            for post in res_json['data']['children']:
                post_data = post['data']

                # break
                for key in keys:
                    try:
                        data[key].append(post_data[key])
                    except:
                        data[key].append('')
                count += 1
            after = res_json['data']['after']
            if after is None:
                break
            params = {'limit': '64', 'after': after}
            bar.update(len(res_json['data']['children']))

    data['created_utc'] = [datetime.datetime.utcfromtimestamp(item) for item in data['created_utc']]
    return pd.DataFrame(data), after

def comments_spider(headers, urls, keys=None):
    if keys is None:
        keys = ['article_url', 'name', 'created_utc', 'parent_id', 'author_fullname', 'author', 'body', 'ups', 'downs']
    data = {key: [] for key in keys}
    for url in tqdm(urls):
        try:
            res = requests.get(url, headers=headers, proxies=proxies)
            comments_dict = res.json()[1]['data']['children']
            print(len(comments_dict))
            for comment in comments_dict:
                comment = comment['data']
                for key in keys[1:]:
                    try:
                        data[key].append(comment[key])
                    except:
                        data[key].append(float('nan'))
                data['article_url'].append(url)
        except KeyboardInterrupt:
            print('user stop')
            break
        except:
            print(f'error in {url}')
            continue
    data['created_utc'] = [datetime.datetime.utcfromtimestamp(item) for item in data['created_utc']]
    return pd.DataFrame(data)




def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config_path', type=str, default='config.yaml')
    parser.add_argument('--task', type=str, choices=['article', 'comments'])
    parser.add_argument('--url', type=str, default='https://oauth.reddit.com/r/depression/')
    parser.add_argument('--data_name', type=str, default='data')
    parser.add_argument('--save_path', type=str, default='./')
    parser.add_argument('--article_num', type=int, default=2000)

    args = parser.parse_args()
    return args


if __name__ == '__main__':

    args = get_args()
    root = os.path.join(args.save_path, args.data_name)
    os.makedirs(root, exist_ok=True)

    headers = log_in(args.config_path)

    if args.task == 'article':
        # 爬取文章
        url = args.url.replace('www', 'oauth')
        if os.path.exists(os.path.join(root, 'task_info.yaml')):
            task_info = yaml.load(os.path.join(root, 'task_info.yaml'))
            after = task_info['after']
        else:
            after = None
        df, after = article_spider(headers, url=url, article_num=args.article_num, after=after)
        df.to_excel(os.path.join(root, 'articles.xlsx'), index=False)
        task_info = {'after': after}
        with open('task_info.yaml', 'w') as f:
            yaml.dump(task_info, f)

    elif args.task == 'comments':
        keys = ['article_url', 'name', 'created_utc', 'parent_id', 'author_fullname', 'author', 'body', 'ups', 'downs']

        root = os.path.join(args.save_path, args.data_name)
        articles_df = pd.read_excel(os.path.join(root, 'articles.xlsx'))
        comments_path = os.path.join(root, 'comments.xlsx')
        if os.path.exists(comments_path):
            comments_df = pd.read_excel(comments_path)
        else:
            comments_df = pd.DataFrame(columns=keys)

        articles_urls = set(['https://oauth.reddit.com' + item for item in list(articles_df['permalink'])])
        comments_urls = set(list(comments_df['article_url']))
        urls = articles_urls - comments_urls

        df = comments_spider(headers, urls, keys)
        pd.concat([comments_df, df]).to_excel(os.path.join(root, 'comments.xlsx'), index=False)













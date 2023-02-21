import requests
import shutil
import sys
import os
import urllib3
import ssl
from bs4 import BeautifulSoup

class DownloadCancelledException(Exception):
    pass


#Needed to get around SSL issue
class CustomHttpAdapter (requests.adapters.HTTPAdapter):
    # "Transport adapter" that allows us to use custom ssl_context.

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = urllib3.poolmanager.PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_context=self.ssl_context)


def get_legacy_session():
    ctx = ssl._create_unverified_context()
    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
    session = requests.session()
    session.mount('https://', CustomHttpAdapter(ctx))
    return session


def get_directory_items(url):
    page = get_legacy_session().get(url,verify=False).text
    soup = BeautifulSoup(page,'html.parser')
    #Remove parent directory and column sorting buttons
    return [node.get('href') for node in soup.find_all('a') if '?' not in node.get('href') and node.string != "Parent Directory"]

#Any item without a '.' is a directory, not a file
#If a directory contains no directories it is a root node
def is_root_node(items):
    return len([item for item in items if '.' not in item]) == 0

#List file should be the only .txt file in a directory
def get_list_file_name(items):
    return [item for item in items if '.txt' in item][0]

def recursive_traverse(url,path):
    items = get_directory_items(url)
    if(is_root_node(items)):
        #Directory contains images
        list_file_name = get_list_file_name(items)
        download_list_file(url,list_file_name,path)
        download_images(url,list_file_name,path)
        return
    
    #Directory contains directories
    for item in items:
        new_directory_path = f"{path}/{item}"
        os.mkdir(new_directory_path)
        recursive_traverse(f"{url}/{item}",new_directory_path)



def download_images(base_url,list_file,base_path):
    with open(f"{base_path}/{list_file}") as f:
        image_names = f.read().split("\n")
    for name in image_names:
        url = f"{base_url}/{name}"
        file = f"{base_path}/{name}"
        #Check file already exists
        if not os.path.exists(file):
            print(f"Downloading: {url}")
            try:
                res = get_legacy_session().get(url,stream = True,verify=False)
                if res.status_code == 200:
                    with open(file,'wb') as f:
                        shutil.copyfileobj(res.raw,f)
            except KeyboardInterrupt:
                print(f"Cancelled downloading:{url}, deleting created file")
                os.remove(file)
                raise DownloadCancelledException
            print(f"Finished downloading: {url}")
    print(image_names)

def download_list_file(base_url,list_file,base_path):
    url = f"{base_url}/{list_file}"
    file = f"{base_path}/{list_file}"
    #Check file already exists
    if not os.path.exists(file):
        print(f"Downloading: {url}")
        try:
            res = get_legacy_session().get(url,verify=False)
            if res.status_code == 200:
                with open(file,'w') as f:
                    f.write(res._content.decode("utf-8"))
        except KeyboardInterrupt:
            print(f"Cancelled downloading:{url}, deleting created file")
            os.remove(file)
            raise DownloadCancelledException
        print(f"Finished downloading: {url}")

if __name__ == "__main__":
    #If no file path is given write to current directory
    if len(sys.argv) > 3:
        file_path = sys.argv[3]
    else:
        file_path = '.'
    try:
        recursive_traverse(sys.argv[1],file_path)
        print("Downloading completed")
    except DownloadCancelledException:
        pass

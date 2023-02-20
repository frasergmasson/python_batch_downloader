import requests
import shutil
import sys
import os
import urllib3
import ssl


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

def download_images(base_url,list_file,base_path):
    with open(list_file) as f:
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
                return
            print(f"Finished downloading: {url}")
    print(image_names)

def download_list_file(base_url,list_file,base_path):
    url = f"{base_url}/{list_file}"
    file = f"{base_path}/{list_file}"
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
            return
        print(f"Finished downloading: {url}")

if __name__ == "__main__":
    #If no file path is given write to current directory
    if len(sys.argv) > 3:
        file_path = sys.argv[3]
    else:
        file_path = '.'
    download_images(sys.argv[1],sys.argv[2],file_path)
"""Bounded-memory S3 transfers. One request carries one raw file."""
from urllib.parse import parse_qs, urlsplit, quote
from boto3.s3.transfer import TransferConfig

MAX_UPLOAD=100*1024*1024


class LimitedInput:
    def __init__(self, stream, length):self.stream=stream;self.remaining=length
    def read(self,size=-1):
        if size==0:return b''
        if self.remaining==0:return b''
        size=self.remaining if size is None or size<0 else min(size,self.remaining)
        data=self.stream.read(size)
        if not data and self.remaining:raise ValueError('Upload ended before its declared size')
        self.remaining-=len(data)
        return data


def parameters(handler):
    p=parse_qs(urlsplit(handler.path).query,keep_blank_values=True)
    bucket=p.get('bucket',[''])[0];key=p.get('key',[''])[0];region=p.get('region',['eu-west-2'])[0]
    if not bucket or not key:raise ValueError('Bucket and object key are required')
    return bucket,key,region,p


def upload(handler,client):
    bucket,key,region,p=parameters(handler)
    size=int(handler.headers.get('Content-Length','-1'))
    if not 0<=size<=MAX_UPLOAD:raise ValueError('Upload files up to 100 MB')
    client('s3',region).upload_fileobj(LimitedInput(handler.rfile,size),bucket,key,
        ExtraArgs={'ContentType':handler.headers.get('Content-Type') or 'application/octet-stream'},
        Config=TransferConfig(multipart_threshold=8*1024*1024,multipart_chunksize=8*1024*1024,use_threads=False))
    handler.reply(200,{'key':key,'bytes':size})


def download(handler,client):
    bucket,key,region,p=parameters(handler);args={'Bucket':bucket,'Key':key}
    if p.get('version'):args['VersionId']=p['version'][0]
    result=client('s3',region).get_object(**args)
    stream=result['Body']
    try:
        handler.send_response(200)
        handler.send_header('Content-Type','application/octet-stream')
        handler.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(key.split('/')[-1] or 'download',safe=''))
        handler.send_header('Content-Length',str(result['ContentLength']))
        handler.send_header('X-Content-Type-Options','nosniff')
        handler.send_header('Cache-Control','no-store')
        handler.end_headers()
        try:
            while True:
                data=stream.read(256*1024)
                if not data:break
                handler.wfile.write(data)
        except Exception:
            handler.close_connection=True
    finally:stream.close()

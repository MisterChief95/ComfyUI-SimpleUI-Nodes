from aiohttp import web
from server import PromptServer

from .version import CONTRACT_VERSION, PACK_NAME, PACK_VERSION


def pack_info():
    return {"pack": PACK_NAME, "version": PACK_VERSION, "contract": CONTRACT_VERSION}


@PromptServer.instance.routes.get("/simpleui/pack")
async def get_pack(request):
    return web.json_response(pack_info())

import requests
import time
import os
import logging

# CONFIG
STEAM_API_KEY = os.environ.get("STEAM_API_KEY")
STEAM_USER_ID = os.environ.get("STEAM_USER_ID")
NOTION_DATABASE_API_KEY = os.environ.get("NOTION_DATABASE_API_KEY")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
# OPTIONAL
include_played_free_games = os.environ.get("include_played_free_games")
enable_item_update = os.environ.get("enable_item_update")
enable_filter = os.environ.get("enable_filter")

# MISC
MAX_RETRIES = 20
RETRY_DELAY = 2
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("")
file_handler = logging.FileHandler("app.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)


def send_request_with_retry(
    url, headers=None, json_data=None, retries=MAX_RETRIES, method="patch"
):
    while retries > 0:
        try:
            if method == "patch":
                response = requests.patch(url, headers=headers, json=json_data)
            elif method == "post":
                response = requests.post(url, headers=headers, json=json_data)
            elif method == "get":
                response = requests.get(url)

            response.raise_for_status()  # 如果响应状态码不是200系列，则抛出HTTPError异常
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"Request Exception occurred: <{e}> Retring....")
            retries -= 1
            if retries > 0:
                time.sleep(RETRY_DELAY)  # 等待一段时间后再重试
            else:
                logger.error("Max retries exceeded. Giving up.")
                return {}


# steamapi
def get_owned_game_data_from_steam():
    url = "http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?"
    url = url + "key=" + STEAM_API_KEY
    url = url + "&steamid=" + STEAM_USER_ID
    url = url + "&include_appinfo=True"
    if include_played_free_games == "true":
        url = url + "&include_played_free_games=True"

    logger.info("fetching data from steam..")

    try:
        response = send_request_with_retry(url, method="get")
        logger.info("fetching data success!")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send request: {e}")


def query_achievements_info_from_steam(game):
    url = "http://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v0001/?"
    url = url + "key=" + STEAM_API_KEY
    url = url + "&steamid=" + STEAM_USER_ID
    url = url + "&appid=" + f"{game['appid']}"
    logger.info(f"querying for {game['name']} achievements counts...")
    response = requests.get(url)
    return response.json()


# notionapi
def add_item_to_notion_database(game, achievements_info):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_DATABASE_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    logger.info(f"adding game {game['name']} to notion...")

    playtime = round(float(game["playtime_forever"]) / 60, 1)
    last_played_time = time.strftime(
        "%Y-%m-%d", time.localtime(game["rtime_last_played"])
    )
    store_url = f"https://store.steampowered.com/app/{game['appid']}"
    icon_url = f"https://media.steampowered.com/steamcommunity/public/images/apps/{game['appid']}/{game['img_icon_url']}.jpg"
    cover_url = f"https://steamcdn-a.akamaihd.net/steam/apps/{game['appid']}/header.jpg"
    total_achievements = achievements_info["total"]
    achieved_achievements = achievements_info["achieved"]

    if total_achievements > 0:
        completion = round(
            float(achieved_achievements) / float(total_achievements) * 100, 1
        )
    else:
        completion = -1

    data = {
        "parent": {
            "type": "database_id",
            "database_id": f"{NOTION_DATABASE_ID}",
        },
        "properties": {
            "name": {
                "type": "title",
                "title": [{"type": "text", "text": {"content": f"{game['name']}"}}],
            },
            "playtime": {"type": "number", "number": playtime},
            "last play": {"type": "date", "date": {"start": last_played_time}},
            "store url": {
                "type": "url",
                "url": store_url,
            },
            "completion": {"type": "number", "number": completion},
            "total achievements": {"type": "number", "number": total_achievements},
            "achieved achievements": {
                "type": "number",
                "number": achieved_achievements,
            },
        },
        "cover": {"type": "external", "external": {"url": f"{cover_url}"}},
        "icon": {"type": "external", "external": {"url": f"{icon_url}"}},
    }

    try:
        response = send_request_with_retry(
            url, headers=headers, json_data=data, method="post"
        )
        logger.info(f"{game['name']} added!")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send request: {e}.")


def query_item_from_notion_database(game):
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_DATABASE_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    logger.info(f"querying {game['name']} from database")
    data = {"filter": {"property": "name", "rich_text": {"equals": f"{game['name']}"}}}

    try:
        response = send_request_with_retry(
            url, headers=headers, json_data=data, method="post"
        )
        logger.info(f"query complete!")
    except Exception as e:
        logger.error(f"Failed to send request: {e}.")
    finally:
        return response.json()


def update_item_to_notion_database(page_id, game, achievements_info):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_DATABASE_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    playtime = round(float(game["playtime_forever"]) / 60, 1)
    last_played_time = time.strftime(
        "%Y-%m-%d", time.localtime(game["rtime_last_played"])
    )
    store_url = f"https://store.steampowered.com/app/{game['appid']}"
    icon_url = f"https://media.steampowered.com/steamcommunity/public/images/apps/{game['appid']}/{game['img_icon_url']}.jpg"
    cover_url = f"https://steamcdn-a.akamaihd.net/steam/apps/{game['appid']}/header.jpg"
    total_achievements = achievements_info["total"]
    achieved_achievements = achievements_info["achieved"]

    if total_achievements > 0:
        completion = round(
            float(achieved_achievements) / float(total_achievements) * 100, 1
        )
    else:
        completion = -1

    logger.info(f"updating {game['name']} to notion...")

    data = {
        "properties": {
            "name": {
                "type": "title",
                "title": [{"type": "text", "text": {"content": f"{game['name']}"}}],
            },
            "playtime": {"type": "number", "number": playtime},
            "last play": {"type": "date", "date": {"start": last_played_time}},
            "store url": {
                "type": "url",
                "url": store_url,
            },
            "completion": {"type": "number", "number": completion},
            "total achievements": {"type": "number", "number": total_achievements},
            "achieved achievements": {
                "type": "number",
                "number": achieved_achievements,
            },
        },
        "cover": {"type": "external", "external": {"url": f"{cover_url}"}},
        "icon": {"type": "external", "external": {"url": f"{icon_url}"}},
    }

    try:
        response = send_request_with_retry(
            url, headers=headers, json_data=data, method="patch"
        )
        logger.info(f"{game['name']} updated!")
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send request: {e}.")


def database_create(page_id):
    url = "https://api.notion.com/v1/databases/"

    headers = {
        "Authorization": f"Bearer {NOTION_DATABASE_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    data = {
        "parent": {
            "type": "page_id",
            "page_id": page_id,
        },
        "title": [{"type": "text", "text": {"content": "Game List"}}],
        "properties": {
            "name": {"title": {}},
            "completion": {"number": {}},
            "playtime": {"number": {}},
            "last play": {"date": {}},
            "total achievements": {"number": {}},
            "achieved achievements": {"number": {}},
            "store url": {"url": {}},
        },
    }

    try:
        response = send_request_with_retry(
            url, headers=headers, json_data=data, method="post"
        )
        return response.json()
    except Exception as e:
        logger.error(f"Failed to send request: {e}")


# MISC
def is_record(game, achievements):
    not_record_time = "2020-01-01 00:00:00"
    time_tuple = time.strptime(not_record_time, "%Y-%m-%d %H:%M:%S")
    timestamp = time.mktime(time_tuple)
    playtime = round(float(game["playtime_forever"]) / 60, 1)

    if (playtime < 0.1 and achievements["total"] < 1) or (
        game["rtime_last_played"] < timestamp
        and achievements["total"] < 1
        and playtime < 6
    ):
        logger.info(f"{game['name']} does not meet filter rule!")
        return False

    return True


def get_achievements_count(game):
    game_achievements = query_achievements_info_from_steam(game)
    achievements_info = {}
    achievements_info["total"] = 0
    achievements_info["achieved"] = 0

    if game_achievements["playerstats"]["success"] is False:
        achievements_info["total"] = -1
        achievements_info["achieved"] = -1
        logger.info(f"no info for game {game['name']}")

    elif "achievements" not in game_achievements["playerstats"]:
        achievements_info["total"] = -1
        achievements_info["achieved"] = -1
        logger.info(f"no achievements for game {game['name']}")

    else:
        achievments_array = game_achievements["playerstats"]["achievements"]
        for achievement_dict in achievments_array:
            achievements_info["total"] = achievements_info["total"] + 1
            if achievement_dict["achieved"]:
                achievements_info["achieved"] = achievements_info["achieved"] + 1

        logger.info(f"{game['name']} achievements count complete!")

    return achievements_info


if __name__ == "__main__":
    owned_game_data = get_owned_game_data_from_steam()

    for game in owned_game_data["response"]["games"]:
        is_add = True
        achievements_info = {}
        achievements_info = get_achievements_count(game)
        if "rtime_last_played" not in game:
            logger.info(f"{game['name']} have no last play time! setting to 0!")
            game["rtime_last_played"] = 0

        if enable_filter == "true" and is_record(game, achievements_info) == False:
            continue

        queryed_item = query_item_from_notion_database(game)
        if "results" not in queryed_item:
            logger.error(f"{game['name']} queryed failed! skipping!")
            continue

        if queryed_item["results"] != []:
            if enable_item_update == "true":
                logger.info(f"{game['name']} already exists!")
                playtime = round(float(game["playtime_forever"]) / 60, 1)

                print(queryed_item["results"][0])

                if queryed_item["results"][0]["playtime"] == playtime:
                    logger.info(f"{game['name']} does not need to update! Skipping!")
                else:
                    logger.info(f"{game['name']} need to update! Updating!")
                    update_item_to_notion_database(
                        queryed_item["results"][0]["id"], game, achievements_info
                    )
            else:
                logger.info(f"{game['name']} already exists! skipping!")
        else:
            logger.info(f"{game['name']} does not exist! creating new item!")
            add_item_to_notion_database(game, achievements_info)

# -*- coding: UTF-8 -*-

import json
import logging
import re
from argparse import ArgumentParser
from datetime import datetime, timedelta
from functools import wraps
from os import PathLike
from pathlib import Path
from time import sleep
from typing import List, Tuple, Union
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.adapters import HTTPAdapter


def empty_retry(times: int = 3, interval: float = 1):
    """Retry when a func returns empty

    Args:
        times (int): Times to retry.
        interval (float): Interval between each retry, in seconds.
    """
    def decorator(func):
        @wraps(func)
        def decorated_func(*args, **kwargs):
            for i in range(times + 1):
                # retry log
                if i > 0:
                    logging.getLogger(__name__).warning("Retry func {} {} time.".format(func.__name__, i))

                # call func
                ret = func(*args, **kwargs)
                if ret:
                    return ret

                # sleep for interval
                sleep(interval)

            # all retry failed
            logging.getLogger(__name__).error("All retries failed in func {}.".format(func.__name__))
            return ret
        return decorated_func
    return decorator


class XSession(requests.Session):
    """A wrapper class for `requests.Session`, can log info.

    If anything wrong happened in a request, return an empty `Response` object, keeping url info and logging error info using `logging` module.
    """

    def __init__(self) -> None:
        """
        Properties:
            interval (float): Seconds between each request. Minimum to 0.01. Default to 0.01
            max_retries (int): max retry times. Default to 3.
            timeout: same as timeout param to `requests.request`, default to 30.
        """
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.interval = 0.01
        self.timeout = 30
        self.max_retries = 3

    @property
    def interval(self):
        return self.__interval

    @interval.setter
    def interval(self, value: float):
        self.__interval = max(0.01, value)

    @property
    def timeout(self):
        return self.__timeout

    @timeout.setter
    def timeout(self, value: Union[Tuple[float, float], float]):
        self.__timeout = value

    @property
    def max_retries(self):
        return self.__max_retries

    @max_retries.setter
    def max_retries(self, value: int):
        self.__max_retries = value
        # set default adapter max retry
        self.mount("https://", HTTPAdapter(max_retries=value))
        self.mount("http://", HTTPAdapter(max_retries=value))

    def request(self, method, url, *args, **kwargs) -> requests.Response:
        sleep(self.interval)
        kwargs.setdefault("timeout", self.timeout)  # timeout to avoid suspended
        try:
            res = super().request(method, url, *args, **kwargs)
        except Exception as e:
            self.logger.error("{}:{}".format(url, e))
            res = requests.Response()
            res.url = url  # keep url info
            return res
        else:
            if not res.ok:
                self.logger.warning("{}:{}".format(url, res.status_code))
            return res


PIXIV_HOSTS = {
    # # PIXIV
    # # *.pximg.net 210.140.92.(138-147)
    "s.pximg.net":      "210.140.92.141",
    "i.pximg.net":      "210.140.92.141",

    # # pixiv DNS
    "ns1.pixiv.net":    "210.140.131.236",
    "ns2.pixiv.net":    "210.140.131.238",

    # # *.pixiv.net 210.140.131.(199-223, 226-229)
    "pixiv.net":        "210.140.131.222",
    "m.pixiv.net":      "210.140.131.222",
    "help.pixiv.net":   "210.140.131.222",
    "factory.pixiv.net": "210.140.131.222",
    "touch.pixiv.net":  "210.140.131.222",
    "p2.pixiv.net":     "210.140.131.222",
    "payment.pixiv.net": "210.140.131.222",
    "ssl.pixiv.net":    "210.140.131.222",
    "chat.pixiv.net":   "210.140.131.222",
    "blog.pixiv.net":   "210.140.131.222",
    "en.dic.pixiv.net": "210.140.131.222",
    "genepixiv.pr.pixiv.net": "210.140.131.222",
    "inside.pixiv.net": "210.140.131.222",

    # # CF but real IP the same as above
    "www.pixiv.net":    "210.140.92.186",
    "fanbox.pixiv.net": "210.140.131.222",
    "goods.pixiv.net":  "210.140.131.222",
    "sensei.pixiv.net": "210.140.131.222",
    "app-api.pixiv.net": "210.140.131.222",

    # # *.pixiv.net 210.140.131.(144-153)
    "imgaz.pixiv.net":  "210.140.131.145",
    "i1.pixiv.net":     "210.140.131.145",
    "comic.pixiv.net":  "210.140.131.145",
    "novel.pixiv.net":  "210.140.131.145",
    "source.pixiv.net": "210.140.131.145",
    "sketch.pixiv.net": "210.140.174.37",

    # # CF unknown real IP
    "accounts.pixiv.net": "210.140.131.222",
    "dev.pixiv.net":    "210.140.131.222",
    "festa.pixiv.net":  "210.140.131.222",
    "times.pixiv.net":  "210.140.131.222",
    "iracon.pixiv.net": "210.140.131.222",
    "matsuri.pixiv.net": "210.140.131.222",
    "doc.pixiv.net":    "210.140.131.222",
    "g-client-proxy.pixiv.net": "210.140.131.222"
}


class PixivBase(XSession):
    # lang=zh
    URL_www = "https://www.pixiv.net"

    # api
    URL_api_login = "https://accounts.pixiv.net/api/login"

    # ajax

    URL_ajax_top_illust = "https://www.pixiv.net/ajax/top/illust"  # ?mode=all|r18 # many many info in index page

    URL_ajax_search_tags = "https://www.pixiv.net/ajax/search/tags/{keyword}"
    # ?order=date&mode=all&p=1&s_mode=s_tag # param for url_search_*
    URL_ajax_search_artworks = "https://www.pixiv.net/ajax/search/artworks/{keyword}"
    URL_ajax_search_illustrations = "https://www.pixiv.net/ajax/search/illustrations/{keyword}"  # ?type=illust
    URL_ajax_search_manga = "https://www.pixiv.net/ajax/search/manga/{keyword}"

    URL_ajax_user = "https://www.pixiv.net/ajax/user/{user_id}"  # user simple info
    URL_ajax_user_following = "https://www.pixiv.net/ajax/user/{user_id}/following"  # ?offset=0&limit=24&rest=show
    URL_ajax_user_recommends = "https://www.pixiv.net/ajax/user/{user_id}/recommends"  # ?userNum=20&workNum=3&isR18=true
    URL_ajax_user_profile_all = "https://www.pixiv.net/ajax/user/{user_id}/profile/all"  # user all illusts and details # 9930155
    URL_ajax_user_profile_top = "https://www.pixiv.net/ajax/user/{user_id}/profile/top"
    URL_ajax_user_illusts = "https://www.pixiv.net/ajax/user/{user_id}/illusts"  # ?ids[]=84502979"

    URL_ajax_illust = "https://www.pixiv.net/ajax/illust/{illust_id}"  # illust details # 70850475
    URL_ajax_illust_pages = "https://www.pixiv.net/ajax/illust/{illust_id}/pages"  # illust pages
    URL_ajax_illust_recommend_init = "https://www.pixiv.net/ajax/illust/{illust_id}/recommend/init"  # limit=1

    URL_ajax_illusts_like = "https://www.pixiv.net/ajax/illusts/like"  # illust_id:""
    URL_ajax_illusts_bookmarks_add = "https://www.pixiv.net/ajax/illusts/bookmarks/add"  # comment:"" illust_id:"" restrict:0 tags:[]

    # php
    URL_php_logout = "https://www.pixiv.net/logout.php"  # ?return_to=%2F
    URL_php_ranking = "https://www.pixiv.net/ranking.php"  # ?format=json&p=1&mode=daily&content=all
    URL_php_rpc_recommender = "https://www.pixiv.net/rpc/recommender.php"  # ?type=illust&sample_illusts=88548686&num_recommendations=500
    URL_php_bookmark_add = "https://www.pixiv.net/bookmark_add.php"  # mode:"add" type:"user" user_id:"" tag:"" restrict:"" format:"json"

    def _check_response(self, res: requests.Response) -> Union[dict, list]:
        """Check response."""

        if res.status_code is None:
            return {}

        try:
            json_ = res.json()
        except ValueError:
            self.logger.error("{}:JsonValueError.".format(res.url))
            return {}

        if json_["error"] is True:
            self.logger.error("{}:{}".format(
                res.url,
                json_.get("message", "") or json_.get("msg", "No msg.")
            ))
            return {}
        return json_["body"]

    def _check_response2(self, res: requests.Response) -> Union[dict, list]:
        """Check response."""

        if res.status_code is None:
            return {}

        try:
            json_ = res.json()
        except ValueError:
            self.logger.error("{}:JsonValueError.".format(res.url))
            return {}

        if "error" in json_:
            self.logger.error("{}:{}".format(res.url, json_["error"]))
            return {}
        return json_

    def __init__(self) -> None:
        """
        Properties:
            domain_fronting (bool): Whether use domain fronting.

        Note:
            When use domain fronting, it will replace `domain` of url to ip address,
            and keep correct `Host` header in headers, and it will NOT verify SSLCertVerification.

            For example:
                url: "https://www.pixiv.net/ajax/top/illust" ==> "https://210.140.131.210/ajax/top/illust"
                headers: {"Host": "www.pixiv.net"}
                verify: False
        """
        super().__init__()
        self.headers["Referer"] = PixivBase.URL_www
        self.domain_fronting = False

    @property
    def domain_fronting(self):
        return self.__domain_fronting

    @domain_fronting.setter
    def domain_fronting(self, value: bool):
        self.__domain_fronting = value
        if value:
            self.logger.warning("Domain fronting is enabled.")

    def request(self, method, url, *args, **kwargs) -> requests.Response:
        if self.domain_fronting:
            components = list(urlsplit(url))

            # add Host header
            if "headers" not in kwargs:
                kwargs["headers"] = {"Host": components[1]}
            else:
                kwargs["headers"]["Host"] = components[1]

            # replace netloc
            components[1] = PIXIV_HOSTS.get(components[1], components[1])

            # NOT verify
            kwargs["verify"] = False

            url = urlunsplit(components)

        return super().request(method, url, *args, **kwargs)

    # GET method

    @empty_retry()
    def _get_page(self, page_url: str) -> bytes:
        """
        Args:
            page_url (str): url to get page from.

        Returns:
            Return empty bytes when failed.
        """
        res = self.get(page_url, stream=True)
        if res.status_code != 200:
            self.logger.error("Failed to get page from {}.".format(page_url))
            return b""  # Need to make bool False
        return res.content

    def _get_top_illust(self, mode="all") -> dict:
        """Get top illusts by mode.

        Args:
            mode: "all" means all ages, "r18" means R-18 only
        """
        res = self.get(
            PixivBase.URL_ajax_top_illust,
            params={"mode": mode}
        )
        return self._check_response(res)

    def _get_search_artworks(self, keyword, order="date_d", mode="all", p=1, s_mode="s_tag", type_="all") -> dict:
        """Get search artworks result

        Args:
            order: "date" means date ascend, "date_d" means date descend
            mode: "all", "safe", "r18"
            p: search result page
            s_mode: "s_tag" partly match tag, "s_tag_full" exactly match tag, "s_tc" match title and character description
            type_: No need to care
        """
        res = self.get(
            PixivBase.URL_ajax_search_artworks.format(keyword=keyword),
            params={
                "order": order,
                "mode": mode,
                "p": p,
                "s_mode": s_mode,
                "type": type_
            }
        )
        return self._check_response(res)

    def _get_search_illustrations(self, keyword, order="date_d", mode="all", p=1, s_mode="s_tag", type_="illust") -> dict:
        """Get search illustration or ugoira result

        Args:
            order: "date" means date ascend, "date_d" means date descend
            mode: "all", "safe", "r18"
            p: search result page
            s_mode: "s_tag" partly match tag, "s_tag_full" exactly match tag, "s_tc" match title and character description
            type_: "illust", "ugoira", "illust_and_ugoira"
        """
        res = self.get(
            PixivBase.URL_ajax_search_illustrations.format(keyword=keyword),
            params={
                "order": order,
                "mode": mode,
                "p": p,
                "s_mode": s_mode,
                "type": type_
            }
        )
        return self._check_response(res)

    def _get_search_manga(self, keyword, order="date_d", mode="all", p=1, s_mode="s_tag", type_="manga") -> dict:
        """Get search manga result

        Args:
            order: "date" means date ascend, "date_d" means date descend
            mode: "all", "safe", "r18"
            p: search result page
            s_mode: "s_tag" partly match tag, "s_tag_full" exactly match tag, "s_tc" match title and character description
            type_: No need to care
        """
        res = self.get(
            PixivBase.URL_ajax_search_manga.format(keyword=keyword),
            params={
                "order": order,
                "mode": mode,
                "p": p,
                "s_mode": s_mode,
                "type": type_
            }
        )
        return self._check_response(res)

    @empty_retry()
    def _get_illust(self, illust_id) -> dict:
        """
        Note:
            `userAccount` is unchangable (for normal user)
            `userName` can change as casual.
            `xRestrict`: 0 is all-age, 1 is R18, 2 is R18-G
        """
        res = self.get(
            PixivBase.URL_ajax_illust.format(illust_id=illust_id),

        )

        return self._check_response(res)

    @empty_retry()
    def _get_illust_pages(self, illust_id) -> list:
        res = self.get(
            PixivBase.URL_ajax_illust_pages.format(illust_id=illust_id)
        )
        return self._check_response(res)

    def _get_illust_recommend_init(self, illust_id, limit=1) -> dict:
        """details.keys()"""
        res = self.get(
            PixivBase.URL_ajax_illust_recommend_init.format(illust_id=illust_id),
            params={"limit": limit}
        )
        return self._check_response(res)

    def _get_user(self, user_id) -> dict:
        res = self.get(
            PixivBase.URL_ajax_user.format(user_id=user_id)
        )

        return self._check_response(res)

    def _get_user_following(self, user_id, offset, limit=50, rest="show") -> dict:
        """Get following list of a user

        Args:
            offset: Start index of list
            limit: Number of list, default to "50", must < 90
            rest(restrict): "show" means "public", "hide" means private, you can just see private followings for your own account

        Returns:
            The list is body.users
        """
        res = self.get(
            PixivBase.URL_ajax_user_following.format(user_id=user_id),
            params={
                "offset": offset,
                "limit": min(limit, 90),
                "rest": rest
            }
        )
        return self._check_response(res)

    def _get_user_recommends(self, user_id, userNum=100, workNum=3, isR18=True) -> dict:
        """Get recommends of a user

        Args:
            userNum: Number of recommends' user, limit to less than 100
            workNum: Unknown
            isR18: Unknown

        Returns:
            Recommends list is body.recommendUsers, the length of list <= userNum
        """
        res = self.get(
            PixivBase.URL_ajax_user_recommends.format(user_id=user_id),
            params={
                "userNum": userNum,
                "workNum": workNum,
                "isR18": isR18
            }
        )
        return self._check_response(res)

    def _get_user_profile_all(self, user_id) -> dict:
        res = self.get(PixivBase.URL_ajax_user_profile_all.format(user_id=user_id))
        return self._check_response(res)

    def _get_user_profile_top(self, user_id) -> dict:
        res = self.get(PixivBase.URL_ajax_user_profile_top.format(user_id=user_id))
        return self._check_response(res)

    @empty_retry()
    def _get_ranking(self, p=1, content="all", mode="daily", date: str = None) -> dict:
        """Get ranking, limit 50 illusts info in one page

        Args:
            p: page number, >= 1
            content:
                "all": mode[Any]
                "illust": mode["daily", "weekly", "daily_r18", "weekly_r18", "monthly", "rookie"]
                "ugoira"(動イラスト): mode["daily", "weekly", "daily_r18", "weekly_r18"]
                "manga": mode["daily", "weekly", "daily_r18", "weekly_r18", "monthly", "rookie"]
            mode: ["daily", "weekly", "daily_r18", "weekly_r18", "monthly", "rookie",
                "original", "male", "male_r18", "female", "female_r18"]
            date: ranking date, example: 20210319, None means the newest

        Note:
            May need cookies to get r18 ranking.
        """
        res = self.get(
            PixivBase.URL_php_ranking,
            params={"format": "json", "p": p, "content": content, "mode": mode, "date": date}
        )

        return self._check_response2(res)

    def _get_logout(self) -> bool:
        """Logout"""
        res = self.get(PixivBase.URL_php_logout, params={"return_to": "/"})
        return True


class Pixiv(PixivBase):
    """"""

    def download_page(self, page_url: str, page_save_path: PathLike) -> bool:
        """Download a single page.

        Args:
            The file path to save.
        """

        page_save_path = Path(page_save_path)
        if page_save_path.is_file() and page_save_path.stat().st_size > 0:
            self.logger.info("Page file {} already exist, skip download.".format(page_save_path.as_posix()))
            return True

        data = self._get_page(page_url)

        if not data:
            self.logger.error("Failed to download page {}.".format(page_url))
            return False

        Path(page_save_path).write_bytes(data)
        return True

    def download_illust(self, illust_id: str, illust_save_folder: PathLike) -> List[Path]:
        """Download all pages of an illust.

        Args:
            illust_id: id of illust.
            illust_save_folder (PathLike): pages where to save.
        The download result may like this:
            <illust_save_folder>/
                <illust_id_p0>
                <illust_id_p1>
                ...

        Returns:
            List[Path]: Successfully downloaded page file path.
        """
        illust_save_folder = Path(illust_save_folder)
        illust_save_folder.mkdir(parents=True, exist_ok=True)

        pages_info = self._get_illust_pages(illust_id)

        if not pages_info:
            self.logger.error("Failed to get pages info and download.")
            return []

        result = []
        flag = True
        for page_info in pages_info:
            page_url: str = page_info["urls"]["original"]
            page_save_path = illust_save_folder.joinpath(page_url.split("/")[-1])
            if not self.download_page(page_url, page_save_path):
                flag = False
                continue
            result.append(page_save_path)

        if flag:
            self.logger.info("Download illust {} all pages success.".format(illust_id))
        else:
            self.logger.warning("Failed to download some pages in illust {}.".format(illust_id))

        return result

    @empty_retry()
    def get_illust(self, illust_id: str) -> dict:
        """Get illust info."""

        illust_info = self._get_illust(illust_id)

        if not illust_info:
            self.logger.error("Failed to get {} illust info.".format(illust_id))
            return {}
        return illust_info

    def get_user_top(self, user_id: str) -> dict:
        """Get user top info."""

        top_info = self._get_user_profile_top(user_id)

        if not top_info:
            self.logger.error("Failed to get user {} top info.".format(user_id))
            return {}
        return top_info

    def get_user_all(self, user_id: str) -> dict:
        """Get user all illust info."""

        all_info = self._get_user_profile_all(user_id)

        if not all_info:
            self.logger.error("Failed to get user {} all info.".format(user_id))
            return {}
        return all_info

    @empty_retry()
    def get_ranking_daily(self, p: int = 1, content: str = "illust", date: str = None, r18: bool = False) -> dict:
        """Get daily ranking info.

        Args:
            p: page num, each page has 50 records.
            content: ["all" | "illust" | "ugoira" | "manga"]
            date: None means newest, or like "20120814".
            r18: Whether only return r18, need to login.
        """

        mode = "daily_r18" if r18 else "daily"
        ranking_info = self._get_ranking(p, content, mode, date)
        if not ranking_info:
            self.logger.error("Failed to get daily ranking info {}:{}:{}:{}.".format(p, content, date, r18))
            return {}
        return ranking_info

    @empty_retry()
    def get_ranking_weekly(self, p: int = 1, content: str = "illust", date: str = None, r18: bool = False) -> dict:
        """Get weekly ranking info.

        Args:
            p: page num, each page has 50 records.
            content: ["all" | "illust" | "ugoira" | "manga"]
            date: None means newest, or like "20120814".
            r18: Whether only return r18, need to login.
        """

        mode = "weekly_r18" if r18 else "weekly"
        ranking_info = self._get_ranking(p, content, mode, date)
        if not ranking_info:
            self.logger.error("Failed to get weekly ranking info {}:{}:{}:{}.".format(p, content, date, r18))
            return {}
        return ranking_info

    @empty_retry()
    def get_ranking_monthly(self, p: int = 1, content: str = "illust", date: str = None) -> dict:
        """Get monthly ranking info.

        Args:
            p: page num, each page has 50 records.
            content: ["all" | "illust" | "manga"]
            date: None means newest, or like "20120814".
        """

        ranking_info = self._get_ranking(p, content, "monthly", date)
        if not ranking_info:
            self.logger.error("Failed to get monthly ranking info {}:{}:{}.".format(p, content, date))
            return {}
        return ranking_info


def get_original_imgurls(pixiv, illust_id, url: str, page_count: int) -> list:
    illust_date = re.search(r"[0-9]{4}/[0-9]{2}/[0-9]{2}/[0-9]{2}/[0-9]{2}/[0-9]{2}", url)
    if not illust_date:
        logging.getLogger(__name__).error(f"datetime not found in {url}")
        return []

    illust_host = "https://i.pximg.net"
    illust_date = illust_date.group()
    urls = []
    for i in range(page_count):
        _urls = {
            "thumb_mini": f"{illust_host}/c/128x128/img-master/img/{illust_date}/{illust_id}_p{i}_square1200.jpg",
            "small": f"{illust_host}/c/540x540_70/img-master/img/{illust_date}/{illust_id}_p{i}_master1200.jpg",
            "regular": f"{illust_host}/img-master/img/{illust_date}/{illust_id}_p{i}_master1200.jpg"
        }

        urlnotype = f"{illust_host}/img-original/img/{illust_date}/{illust_id}_p{i}"
        ftype = "jpg"
        for t in ("jpg", "png", "gif"):
            if pixiv.head(f"{urlnotype}.{t}").status_code == 200:
                ftype = t
                break

        _urls["original"] = f"{urlnotype}.{ftype}"

        urls.append({
            "urls": _urls,
            "width": 0,
            "height": 0
        })

    return urls


def get_top10_details(type_: str = "monthly", date: str = None) -> dict:
    """"""
    pixiv = Pixiv()
    pixiv.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0"
    })

    ### DEBUG ###
    # pixiv.proxies.update({
    #     "http": "http://127.0.0.1:10809",
    #     "https": "http://127.0.0.1:10809"
    # })

    if type_ == "monthly":
        ranking_data = pixiv.get_ranking_monthly(date=date)
    elif type_ == "weekly":
        ranking_data = pixiv.get_ranking_weekly(date=date)
    else:
        ranking_data = pixiv.get_ranking_daily(date=date)

    illusts = []
    for content in ranking_data["contents"][:10]:
        illust_id = content["illust_id"]
        illust_info = pixiv.get_illust(illust_id)
        illust_urls = pixiv._get_illust_pages(illust_id)

        # 手动生成 illust_info 里的 url
        if not illust_urls:
            logging.getLogger(__name__).warning(f"Try to generate url for illust {illust_id}")
            illust_urls = get_original_imgurls(pixiv, illust_id, content["url"], int(content["illust_page_count"]))

        illusts.append({
            "illustId": illust_info["illustId"],
            "illustTitle": illust_info["illustTitle"],
            "restrict": illust_info["restrict"],
            "xRestrict": illust_info["xRestrict"],
            "sl": illust_info["sl"],
            "urls": illust_urls,
            "tags": [t["tag"] for t in illust_info["tags"]["tags"]],
            "userId": illust_info["userId"],
            "userName": illust_info["userName"],
        })

    return {
        "type": type_,
        "date": ranking_data["date"],
        "illusts": illusts
    }


if __name__ == "__main__":
    datelist = set()
    for t in ("monthly", "weekly", "daily"):
        data = get_top10_details(t)
        path = Path(data["date"][0:4], data["date"][4:6], data["date"][6:8], f"{t}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

        datelist.add(data["date"])

    datelist.update(Path("index.txt").read_text().splitlines())
    Path("index.txt").write_text("\n".join(sorted(datelist, reverse=True)))

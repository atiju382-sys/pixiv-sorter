from pixivpy3 import AppPixivAPI
import os

api = AppPixivAPI()
with open("refresh_token.txt", "r") as f:
    token = f.read().strip()
api.auth(refresh_token=token)

print("Testing search 'original' with sort='date_desc'...")
json_result = api.search_illust("original", sort="date_desc")
if json_result.illusts:
    print(f"First image likes: {json_result.illusts[0].total_bookmarks}")
    print(f"Second image likes: {json_result.illusts[1].total_bookmarks}")
else:
    print("No results for date_desc")

print("\nTesting search 'original' with sort='popular_desc'...")
json_result = api.search_illust("original", sort="popular_desc")
if json_result.illusts:
    print(f"First image likes: {json_result.illusts[0].total_bookmarks}")
else:
    print("No results for popular_desc (likely requires Premium)")

print("\nTesting user bookmarks (just to verify auth works fully)...")
json_result = api.user_bookmarks_illust(api.user_id)
if json_result.illusts:
    print(f"User has bookmarks: {len(json_result.illusts)}")
else:
    print("User has no bookmarks or failed.")

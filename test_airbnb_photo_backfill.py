import io
from PIL import Image

from airbnb_photo_backfill_core import (
    extract_muscache_candidates,
    dhash_bytes,
    hamming_distance,
    choose_additional_candidates,
    insert_additional_photos_line,
)


def _img_bytes(seed=0, tweak=False):
    im = Image.new('RGB', (32, 32), 'white')
    px = im.load()
    for y in range(32):
        for x in range(32):
            v = (x * 7 + y * 11 + seed * 13) % 256
            if tweak and x == 10 and y == 10:
                v = (v + 3) % 256
            px[x, y] = (v, (v * 3) % 256, (v * 5) % 256)
    b = io.BytesIO(); im.save(b, format='JPEG', quality=92); return b.getvalue()


def test_extracts_unique_listing_image_urls_and_excludes_platform_assets():
    html = r'''
      {"photo":"https:\/\/a0.muscache.com\/im\/pictures\/miso\/Hosting-123\/original\/aaa.jpeg?im_w=720"}
      <img src="https://a0.muscache.com/im/pictures/miso/Hosting-123/original/aaa.jpeg?im_w=480">
      <img src="https://a0.muscache.com/im/pictures/hosting/Hosting-123/original/bbb.jpg?im_w=720&amp;x=1">
      <img src="https://a0.muscache.com/im/pictures/airbnb-platform-assets/Foo/original/icon.png?im_w=240">
      <img src="https://a0.muscache.com/im/pictures/AirbnbPlatformAssets/UserProfile/original/avatar.png?im_w=120">
    '''
    assert extract_muscache_candidates(html) == [
        'https://a0.muscache.com/im/pictures/miso/Hosting-123/original/aaa.jpeg',
        'https://a0.muscache.com/im/pictures/hosting/Hosting-123/original/bbb.jpg',
    ]


def test_dhash_is_stable_for_near_identical_recompression():
    a = dhash_bytes(_img_bytes(2, False))
    b = dhash_bytes(_img_bytes(2, True))
    assert hamming_distance(a, b) <= 4


def test_choose_additional_candidates_excludes_reference_matches_and_duplicate_candidates():
    ref = _img_bytes(1)
    same = _img_bytes(1, True)
    extra = _img_bytes(7)
    extra_dup = _img_bytes(7)
    candidates = [('u1', same), ('u2', extra), ('u3', extra_dup)]
    out = choose_additional_candidates([ref], candidates, threshold=4)
    assert [u for u, _ in out] == ['u2']


def test_insert_additional_photos_line_before_hashtags_and_idempotent():
    text = 'Описание\n\n👤 Оператор: @cozy_asia\n\n#Самуи #CozyAsia'
    url = 'https://drive.google.com/drive/folders/abc'
    updated = insert_additional_photos_line(text, url)
    assert updated == (
        'Описание\n\n👤 Оператор: @cozy_asia\n\n'
        '📸 Дополнительные фото\n\n#Самуи #CozyAsia'
    )
    assert insert_additional_photos_line(updated, url) == updated

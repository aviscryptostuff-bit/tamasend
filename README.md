# TamaOS

Send items, Gotchi Points and a marriage partner to a Tamagotchi On / Meets over Bluetooth. You don't need the official app.

The site (`index.html`) has three tabs:

- **Shop:** every item from MyMeets (484 English, 365 Japanese): wallpapers, food, items, accessories, games and stations. You can send any of them with Gotchi Points.
- **Custom:** our own pistol, skateboard, pizza and burger, a wallpaper made from your photo, or any item file.
- **Marry:** build a partner from body, face, head and back parts in 13 color sets, then marry your adult Tama. This is MyMeets' Marriage feature.

Everything we've learned so far is in [HANDOFF.md](HANDOFF.md).

## Put the site online

Upload **`index.html` and the whole `data` folder** to the repo. The Shop and Marry tabs read their pictures from `data/`.

1. On GitHub, open this repo and go to **Settings → Pages**.
2. Under **Build and deployment**, choose **Deploy from a branch**. Pick **main** and **/ (root)**, then tap **Save**.
3. Wait a minute or two. The site will be at **https://aviscryptostuff-bit.github.io/tamasend/**.

## Send from iPhone

1. Install **Bluefy** from the App Store. Safari can't use Bluetooth.
2. Open the link above **in Bluefy**.
3. On the Tama, pick **Connection → APP**, press back, then pick **Connection → Download**. The Tama's clock has to be set to daytime.
4. Pick an item, set the coins, tap **Connect & send** and choose **TMGC_meets**.
5. If it fails, tap **Copy log** and send a screenshot or the log text.

The Marry tab has its own two steps on the page. First your Tama visits, then it comes back married.

## Send from a PC

```
pip install bleak
python pc/tamaos_send.py items/wallpaper_bg50001.txt --points 50
```

## Changing the site

Edit `tools/page.html`, then run `python tools/build_page.py`. This writes `index.html` with the starter wallpaper, presets, color sets and DNA tables filled in. `tools/make_data.py <MyMeets assets folder> data` rebuilds the `data` folder.

from PIL import Image
import imagehash, torch, random, os
import numpy as np
from requests import RequestException

import utility.deep_danbooru_model as deep_danbooru_model
import utility.maid_classifier_model as maid_classifier_model
import utility.dscrape as dscrape
import utility.gpt as gpt

print("Loading Deep Danbooru...")
DD = deep_danbooru_model.DeepDanbooruModel()
DD.load_state_dict(torch.load('./models/model-resnet_custom_v3.pt'))
DD.eval().half().cuda()

print("Loading Maid Classifier...")
MCNN = maid_classifier_model.MCNN()
MCNN.load_state_dict(torch.load('./models/maidel_E22.pth'))
MCNN.eval().cuda()

def MCNN_check_is_maid(img : Image):
  processed = maid_classifier_model.preprocess_image(img)
  probs = maid_classifier_model.predict_image(processed, MCNN)
  probs = probs.squeeze().tolist()
  return probs[0] > 0.90
 

def DD_get_tags(img : Image):
  img = img.convert("RGB").resize((512, 512))
  a = np.expand_dims(np.array(img, dtype=np.float32), 0) / 255

  with torch.no_grad(), torch.autocast("cuda"):
    x = torch.from_numpy(a).cuda()
    y = DD(x)[0].detach().cpu().numpy()

  exclude_tags = {"open_mouth", "closed_mouth", "visible_eyebrows", "alternate_costume", "rating:safe"}
  tags_list = [{"tag": DD.tags[i], "prob": p} for i, p in enumerate(y) if p >= 0.65 and DD.tags[i] not in exclude_tags]

  return tags_list[:30]

def generate_messages_from_new_links():
  print("INFO: Running generate_messages_from_new_links()")
  new_links = dscrape.get_new_links_from_front_page()

  if not new_links:
    print("INFO: No new links, exiting.")
    return None

  #filter out links with proper maids
  maids = []

  for link in new_links:
    try:
      img = dscrape.get_image_from_page_link(link)
      if not img:
        raise ValueError(f"INFO: {link} does not contain a valid image")
    except ValueError as e:
      print(f"EXCEPTION: {link} does not contain a valid image, continuing")
      print(e)
      with open("global_seen_links.txt", "a") as f:
        f.write(str(link) + "\n")
      continue
    except RequestException as e:
      raise e

    if MCNN_check_is_maid(img):
      print(f"INFO: Found maid from: {link}")
      maids.append(img)

    #save link as seen
    with open("global_seen_links.txt", "a") as f:
      f.write(str(link) + "\n")

    if len(maids) > 0:
      break
  
  if len(maids) == 0:
    print("INFO: Checked all new links, but found no maids, exiting.")
    return None
  
  #double check that maids are not in posted_images.txt
  posted_images = open("global_posted_images.txt").read()
  maids = [maid for maid in maids if str(imagehash.average_hash(maid)) not in posted_images]
  if len(maids) == 0:
    #if all maids are in global_posted_images.txt, return None
    print("INFO: Already posted all new links, exiting.")
    return None

  #messages contains a list of tuples with the image and the text
  messages = []
  for maid_img in maids:
    tags = DD_get_tags(maid_img)
    print("Sending tags to GPT...")
    try:
      response = gpt.summarize_image_from_tags(tags)
      pass
    except Exception as e:
      print("EXCEPTION: logic.generate_messages_from_new_links() failed to get response from GPT")
      raise e
    #response = "test"
    print("got response from GPT.")
    messages.append((maid_img, response))

  return messages


def post_maid_with_commentary(guild_id : int):
  print("Downloading images...")

  maid_img = None
  interaction_guild_posted_images = open(os.path.join("server_post_history", str(guild_id), "posted_images.txt")).read()

  loops = 0
  while(maid_img is None):
    page = random.randint(5, 700)
    print("Downloading images from page " + str(page) + "...")
    links = dscrape.get_search_page_links(f"https://danbooru.donmai.us/posts?page={page}&tags=maid+rating%3Ageneral")

    for link in links:
      try:
        img = dscrape.get_image_from_page_link(link)
      except Exception as e:
        print("Failed to get image from " + link)
        print(e)
        continue
      if img:
        print("Got image from " + link)
        if MCNN_check_is_maid(img) and str(imagehash.average_hash(img)) not in interaction_guild_posted_images:
          maid_img = img
          print("Found maid, posting...")
          break
    loops += 1

    if loops > 5:
      print("ERROR: Failed to find maid after 5 tries, exiting.")
      return None, "Something went wrong."

  print("INFO: Getting tags from Deep Danbooru...")
  tags = DD_get_tags(maid_img)
  print(tags)

  print("INFO: Sending tags to GPT...")
  response = gpt.summarize_image_from_tags(tags)
  print("INFO: Got response from GPT.")

  return maid_img, response
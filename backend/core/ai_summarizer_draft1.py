"""
Summarizer — uses BART locally (free, no API key).
Falls back to extractive if model unavailable.
"""

import re #regular expression
import logging # for debugging purposes

log = logging.getLogger(__name__) 

MODEL        = "facebook/bart-large-cnn" #model name
MAX_INPUT    = 600 #maximum input 
MIN_TOKENS   = 40 #minimum number of words as answer
MAX_TOKENS   = 120 #max no of words as answer
FB_SENTENCES = 3 # I don't have clue

_pipeline = None #pipeline


def _load(): #loading the model
    global _pipeline #making the variable global, 
    if _pipeline is not None: #lazy initialization
        return _pipeline
    try:
        from transformers import pipeline #importing the pipeline from transformers
        log.info(f"Loading AI model '{MODEL}'...") 
        _pipeline = pipeline("summarization", model=MODEL, device=-1, framework="pt")  #constructing the AI model
        log.info("✅ AI model ready.")
    except Exception as e:
        log.warning(f"⚠️  Could not load AI model: {e}") #If any problem occurs, say "couldn't load AI model"
        _pipeline = None #set pipeline to None
    return _pipeline #returning the model


def _ai_summarize(text: str): #ai inference
    pipe = _load() #pipe refers to the model
    if pipe is None: 
        return None
    words = text.split() #splitting the text into words
    if len(words) < 50: #if the sentence is less than 50
        return None #we return nothing
    truncated = " ".join(words[:MAX_INPUT]) #If words are more than 600 (approximately), then we truncate and get the first 600 words
    try:
        result = pipe(truncated, min_length=MIN_TOKENS, max_length=MAX_TOKENS, do_sample=False, truncation=True) #generate minimum 40 and maximum 120 tokens
        return result[0]["summary_text"].strip() or None #this returns the result
    except Exception as e:
        log.warning(f"AI inference failed: {e}") #show error in case inference fails
        return None


def _extractive(text: str, n: int = FB_SENTENCES) -> str: #this is plan B. Split the sentences and keep the long ones. FB_sentences is the max amount of sentences 
    if not text: #if texts doesn't exist
        return "" #return blank thing
    sentences = re.split(r'(?<=[.!?])\s+', text.strip()) #split the sentences
    kept = [] #initializing the array of sentences keep
    for s in sentences:
        s = s.strip() #deleting the blanks
        if len(s) < 40: #if the sentence has lower than 40 characters, don't add the sentence
            continue
        if any(skip in s.lower() for skip in ["cookie", "subscribe", "sign up", "newsletter", "advertisement"]): #if there exists these words, don't add
            continue
        kept.append(s) #add the sentence
        if len(kept) >= n:
            break # if the max number of sentences are reached, then stop
    return " ".join(kept) #returning an unstructured text


def summarize(text: str) -> dict: #summarization of the text by the AI (wrapper)
    ai_result = _ai_summarize(text) # AI inference
    if ai_result: #if result exists
        return {"summary": ai_result, "method": "ai"} #return dict
    fallback = _extractive(text) #fallback method (plan B)
    return {"summary": fallback if fallback else "No summary available.", "method": "fallback"} #return dict

#DONE
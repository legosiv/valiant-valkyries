import json
import math
import os
import random
from collections import namedtuple
from typing import List, Tuple

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

BLOCK_SIZE = 20
CANVAS_HEIGHT = 500
CANVAS_WIDTH = 500
app = FastAPI()
init_snake_size = 3
init_difficulty = 3*1000  # time in milliseconds
leaderboard = []
# leaderboard will be sorted by this key
LEADERBOARD_SORT_BY = "score"
BACKEND = os.path.join(os.getcwd(), "frontend")


with open("env.json") as j:
    env = json.load(j)
    # todo add the env values to the app
    print(env)


@app.websocket_route("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Websocket server endpoint.

    This is where a websocket connection is made
    and it is used to send and recive data to the client.
    """
    await websocket.accept()
    snake_position = []
    score = 0
    snake_size = init_snake_size
    difficulty = init_difficulty
    leaderboard = load_leaderboard()
    # Send food list to client
    foods_list = food_list()
    await send_food_list(websocket, foods_list)
    try:
        while True:

            # Recive data from client
            receive_data = await websocket.receive_json()
            # print(receive_data)

            if "info" in receive_data:
                snake_position = receive_data["info"]["snake_pos"]
                score = receive_data["info"]["score"]
                print("Snake position: ", snake_position, "| Score: ", score)

            if "food_eaten" in receive_data:
                food_eaten = foods_list[receive_data["food_eaten"]]
                if food_eaten[3] == 0:
                    # reduce gameplay difficulty
                    difficulty += 2000
                    await update_difficulty(websocket, difficulty)
                elif food_eaten[3] == 1:
                    # increase snake size
                    snake_size += 4
                else:
                    # normal food
                    snake_size += 1
                del foods_list[receive_data["food_eaten"]]
                foods_list.append(food := create_food(score))
                await send_single_food(websocket, food)

            if "save" in receive_data:
                score_data = receive_data["save"]
                leaderboard = save_score(score_data, leaderboard)
                await send_leaderboard(websocket, leaderboard)
                print("leaderboard: ", leaderboard)
                await websocket.close()

            if "Game_Over" in receive_data:
                await send_leaderboard(websocket, leaderboard)
                print("Gameover: ", receive_data["Game_Over"])
                snake_position = []
                score = 0
                snake_size = 3

    except Exception as e:
        if (e == WebSocketDisconnect):
            print("Connection closed by client")
        else:
            print("Error: ", e)


async def send_food_list(socket: WebSocket, food_list: List[List[int]]) -> None:
    """Send created food list to client."""
    await socket.send_json({"food_list": food_list})


async def send_single_food(socket: WebSocket, food: List[int]) -> None:
    """Send single created food data to client."""
    await socket.send_json({"food": food})


async def send_leaderboard(socket: WebSocket, leaderboard: List[Tuple]) -> None:
    """Send leaderboard data to client."""
    await socket.send_json({"leaderboard": leaderboard})


async def update_difficulty(socket: WebSocket, difficulty: int) -> None:
    """Send difficulty update data to client."""
    await socket.send_json({"difficulty": difficulty})


def create_food(score: int) -> List[int]:
    """
    Create one food item for snake to consume.

    List of the form [postion_x, position_y, direction, food_type].
    """
    ran = random.SystemRandom()
    r = math.floor(ran.random() * CANVAS_WIDTH)
    food_x = r - BLOCK_SIZE
    r = math.floor(ran.random() * CANVAS_HEIGHT)
    food_y = r - BLOCK_SIZE
    food_direction = math.floor(ran.random() * 4)  # up, down, left, right
    foodtype = food_type(score)
    return [food_x, food_y, food_direction, foodtype]


def food_type(score: int) -> int:
    """
    Return food type depending on score and rarity.

    Food type is either 0, 1, 2 or 3.
    """
    FoodType = namedtuple("FoodType", ["min_score", "rarity", "food_type"])
    hp1_food = FoodType(0, 0, 3)
    hp4_food = FoodType(3000, 50, 1)
    feature_food = FoodType(6000, 75, 2)
    time_food = FoodType(9000, 90, 0)

    ran = random.SystemRandom()
    if score >= time_food.min_score:
        if ran.random() > time_food.rarity:
            return time_food.food_type
    elif score >= feature_food.min_score:
        if ran.random() > feature_food.rarity:
            return feature_food.food_type
    elif score >= hp4_food.min_score:
        if ran.random() > hp4_food.rarity:
            return hp4_food.food_type
    else:
        return hp1_food.food_type


def food_list() -> List[List[int]]:
    """
    Create a list of food items for snake to consume.

    List of the form [food, food, food ...].
    """
    food_list = []
    for _ in range(5):
        food = create_food(0)
        food_list.append(food)
    # print(food_list)
    return food_list


def save_score(data: dict, list: List) -> List[tuple]:
    """Save the score for a user into leaderboard.

    Leaderboard is sorted by score in descending order.
    """
    # check if the user is already in the leaderboard
    if data["user"] in [row[0] for row in list]:
        # if so, update the score of the user
        for row in list:
            if row[0] == data["user"]:
                # check if the score is higher than the previous one
                if data["score"] > row[1]:
                    entry = tuple(data.values())
                    list.remove(row)
                    break
                    # todo send the client a message that the score was higher
                # if not, discard the score
                else:
                    # todo send the client a message that the score was lower
                    entry = None
    # if not, add the user to the leaderboard
    else:
        # convert dict to tuple of its values
        entry = tuple(data.values())

    # check if the entry is not None//if the score is lower than the previous one
    if entry is not None:
        list.append(entry)
        # sort by score in descending order
        list.sort(key=lambda x: x[1], reverse=True)
        save_score_to_file(list)
    return list


def save_score_to_file(data: list) -> None:
    """Save the leaderboard into leaderboard.json."""
    # convert list of tuples to list of dicts
    data = [dict(zip(data[0], row)) for row in data]
    # create dict to load file values
    file_data = dict()
    with open('leaderboard.json', 'r+') as f:
        file_data = json.load(f)
        f.seek(0)
        # append new data and delete old data
        file_data.update({"user_scores": data})
        f.truncate(0)
        json.dump(file_data, f, indent=4)
        f.close()


def load_leaderboard() -> List[Tuple]:
    """Load leaderboard from file."""
    with open('leaderboard.json', 'r') as f:
        leaderboard = json.load(f)
        f.close()
    leaderboard = leaderboard["user_scores"]
    for i, row in enumerate(leaderboard):
        leaderboard[i] = tuple(row.values())
    return leaderboard


app.mount("/game", StaticFiles(directory="frontend", html=True), name="game")


def start() -> None:
    """Launched with `poetry run start` at root level"""
    uvicorn.run("backend.main:app", port=8000, log_level="info", reload=True)

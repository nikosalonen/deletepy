# create array of user_ids
import requests
import time
import sys

#token from parameter. if missing, exit and print error
if len(sys.argv) < 3:
    print("Missing token")
    exit(1)

token = sys.argv[2]

#read user_ids from parameter csv file and put them to array. if missing, exit and print error
if len(sys.argv) < 2:
    print("Missing user ids")
    exit(1)
user_ids = []
with open(sys.argv[1], 'r') as f:
    for line in f:
        user_ids.append(line.strip())

# create function to delete user by id
def delete_user(id):
    print("Deleting user: " + id)
    # url to delete user from auth0 + id
    url = "https://tunnus-dev.almamedia.net/api/v2/users/"+ id
    # headers to send to auth0
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
    }
    # body to send to auth0
    body = {
        "id": id
    }
    # send request to auth0
    response = requests.delete(url, headers=headers)
    # wait for the response and print the response
    print(response.text)




# for each user_ids in the array run the delete function once per second
for id in user_ids:
    delete_user(id)
    time.sleep(1)

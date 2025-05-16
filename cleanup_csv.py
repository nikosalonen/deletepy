import csv

with open('ids.csv', newline='') as infile:
    reader = csv.DictReader(infile)
    usernames = []
    for row in reader:

        if '_at_' in row['userName']:
            usernames.append(row['userName'].replace('_at_', '@'))
        else:
            usernames.append(row['userId'])

with open('ids.csv', 'w', newline='') as outfile:
    for username in usernames:
        outfile.write(f"{username}\n")

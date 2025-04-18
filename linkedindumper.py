import requests
import random
import json
import re
import argparse
from argparse import RawTextHelpFormatter
import sys
import time
import unidecode
from datetime import datetime
import urllib.parse
import textwrap
import threading

# You may store your session cookie here persistently
li_at = "YOUR-COOKIE-VALUE"

# Converting German umlauts
special_char_map = {ord('ä'):'ae', ord('ü'):'ue', ord('ö'):'oe', ord('ß'):'ss'}

format_examples = '''
--email-format '{0}.{1}@example.com' --> john.doe@example.com
--email-format '{0[0]}.{1}@example.com' --> j.doe@example.com
--email-format '{1}@example.com' --> doe@example.com
--email-format '{0}@example.com' --> john@example.com
--email-format '{0[0]}{1[0]}@example.com' --> jd@example.com
'''

parser = argparse.ArgumentParser("linkedindumper.py", formatter_class=RawTextHelpFormatter)
parser.add_argument("--url", metavar='<linkedin-url>', help="A LinkedIn company url - https://www.linkedin.com/company/<company>", type=str, required=True)
parser.add_argument("--cookie", metavar='<cookie>', help="LinkedIn 'li_at' session cookie", type=str, required=False)
parser.add_argument("--quiet", help="Show employee results only", required=False, action='store_true')
parser.add_argument("--include-private-profiles", help="Show private accounts too", required=False, action='store_true')
parser.add_argument("--jitter", help="Add a random jitter to HTTP requests", required=False, action='store_true'),
parser.add_argument("--output", "-o", metavar='<filename>', help="Output file", required=False, type=str)
parser.add_argument("--format", "-f", help="Result format", choices=['csv','json'], default='csv' ,required=False)
parser.add_argument("--email-format", metavar='<format>', help="Python string format for emails; for example:"+format_examples, required=False, type=str)

args = parser.parse_args()
url = args.url

# Optional CSRF token, not needed for GET requests but still defined to be sure
JSESSIONID = "ajax:5739908118104050450"

# Overwrite variables if set via CLI
if args.cookie:
	li_at = args.cookie

if args.email_format:
	mailformat = args.email_format
else:
	mailformat = False

headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:102.0) Gecko/20100101 Firefox/102.0', 'Content-type': 'application/json', 'Csrf-Token': JSESSIONID}
cookies_dict = {"li_at": li_at, "JSESSIONID": JSESSIONID}

def print_logo():
	print("""\

 ██▓     ██▓ ███▄    █  ██ ▄█▀▓█████ ▓█████▄  ██▓ ███▄    █ ▓█████▄  █    ██  ███▄ ▄███▓ ██▓███  ▓█████  ██▀███  
▓██▒    ▓██▒ ██ ▀█   █  ██▄█▒ ▓█   ▀ ▒██▀ ██▌▓██▒ ██ ▀█   █ ▒██▀ ██▌ ██  ▓██▒▓██▒▀█▀ ██▒▓██░  ██▒▓█   ▀ ▓██ ▒ ██▒
▒██░    ▒██▒▓██  ▀█ ██▒▓███▄░ ▒███   ░██   █▌▒██▒▓██  ▀█ ██▒░██   █▌▓██  ▒██░▓██    ▓██░▓██░ ██▓▒▒███   ▓██ ░▄█ ▒
▒██░    ░██░▓██▒  ▐▌██▒▓██ █▄ ▒▓█  ▄ ░▓█▄   ▌░██░▓██▒  ▐▌██▒░▓█▄   ▌▓▓█  ░██░▒██    ▒██ ▒██▄█▓▒ ▒▒▓█  ▄ ▒██▀▀█▄  
░██████▒░██░▒██░   ▓██░▒██▒ █▄░▒████▒░▒████▓ ░██░▒██░   ▓██░░▒████▓ ▒▒█████▓ ▒██▒   ░██▒▒██▒ ░  ░░▒████▒░██▓ ▒██▒
░ ▒░▓  ░░▓  ░ ▒░   ▒ ▒ ▒ ▒▒ ▓▒░░ ▒░ ░ ▒▒▓  ▒ ░▓  ░ ▒░   ▒ ▒  ▒▒▓  ▒ ░▒▓▒ ▒ ▒ ░ ▒░   ░  ░▒▓▒░ ░  ░░░ ▒░ ░░ ▒▓ ░▒▓░
░ ░ ▒  ░ ▒ ░░ ░░   ░ ▒░░ ░▒ ▒░ ░ ░  ░ ░ ▒  ▒  ▒ ░░ ░░   ░ ▒░ ░ ▒  ▒ ░░▒░ ░ ░ ░  ░      ░░▒ ░      ░ ░  ░  ░▒ ░ ▒░
  ░ ░    ▒ ░   ░   ░ ░ ░ ░░ ░    ░    ░ ░  ░  ▒ ░   ░   ░ ░  ░ ░  ░  ░░░ ░ ░ ░      ░   ░░          ░     ░░   ░ 
    ░  ░ ░           ░ ░  ░      ░  ░   ░     ░           ░    ░       ░            ░               ░  ░   ░     
                                      ░                      ░                                         ░ by LRVT      
	""")

def show_loading_message(stop_event):
	loading_message = "Please be patient"
	while not stop_event.is_set():
		for _ in range(3):
			if stop_event.is_set():
				break
			for dot in range(4):
				sys.stdout.write("\r" + loading_message + "." * dot + " " * (3 - dot))
				sys.stdout.flush()
				time.sleep(0.5)

def get_company_id(company):
	company_encoded = urllib.parse.quote(company)
	api1 = f"https://www.linkedin.com/voyager/api/voyagerOrganizationDashCompanies?decorationId=com.linkedin.voyager.dash.deco.organization.MiniCompany-10&q=universalName&universalName={company_encoded}"
	r = requests.get(api1, headers=headers, cookies=cookies_dict, timeout=200)
	response1 = r.json()
	company_id = response1["elements"][0]["entityUrn"].split(":")[-1]
	return company_id

def get_employee_data(company_id, start, count=10):
	api2 = f"https://www.linkedin.com/voyager/api/search/dash/clusters?decorationId=com.linkedin.voyager.dash.deco.search.SearchClusterCollection-165&origin=COMPANY_PAGE_CANNED_SEARCH&q=all&query=(flagshipSearchIntent:SEARCH_SRP,queryParameters:(currentCompany:List({company_id}),resultType:List(PEOPLE)),includeFiltersInResponse:false)&count={count}&start={start}"
	r = requests.get(api2, headers=headers, cookies=cookies_dict, timeout=200)
	response2 = r.json()
	return response2

def clean_data(data):
	emoj = re.compile("["
				u"\U0001F600-\U0001F64F"  # emoticons
				u"\U0001F300-\U0001F5FF"  # symbols & pictographs
				u"\U0001F680-\U0001F6FF"  # transport & map symbols
				u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
				u"\U00002500-\U00002BEF"  # chinese char
				u"\U00002702-\U000027B0"
				u"\U00002702-\U000027B0"
				u"\U000024C2-\U0001F251"
				u"\U0001f926-\U0001f937"
				u"\U00010000-\U0010ffff"
				u"\u2640-\u2642" 
				u"\u2600-\u2B55"
				u"\u200d"
				u"\u23cf"
				u"\u23e9"
				u"\u231a"
				u"\ufe0f"  # dingbats
				u"\u3030"
									"]+", re.UNICODE)
	
	cleaned = re.sub(emoj, '', data).strip()
	cleaned = cleaned.replace('Ü','Ue').replace('Ä','Ae').replace('Ö', 'Oe').replace('ü', 'ue').replace('ä', 'ae').replace('ö', 'oe')
	cleaned = cleaned.replace(',', '')
	cleaned = cleaned.replace(';', ',')
	cleaned = unidecode.unidecode(cleaned)
	return cleaned.strip()

def parse_employee_results(results):
	employee_dict = []

	for employee in results:
		try:
			account_name = clean_data(employee["itemUnion"]['entityResult']["title"]["text"]).split(" ")
			badwords = ['Prof.', 'Dr.', 'M.A.', ',', 'LL.M.']
			for word in list(account_name):
				if word in badwords:
					account_name.remove(word)

			if len(account_name) == 2:
				firstname = account_name[0]
				lastname = account_name[1]
			else:
				firstname = ' '.join(map(str, account_name[0:(len(account_name)-1)]))
				lastname = account_name[-1]
		except:
			continue

		try:
			position = clean_data(employee["itemUnion"]['entityResult']["primarySubtitle"]["text"])
		except:
			position = "N/A"
		
		gender = "N/A"

		try:
			location = employee["itemUnion"]['entityResult']["secondarySubtitle"]["text"]
		except:
			location = "N/A"

		try:
			profile_link = employee["itemUnion"]['entityResult']["navigationUrl"].split("?")[0]
		except:
			profile_link = "N/A"

		if args.include_private_profiles:
			employee_dict.append({"firstname": firstname, "lastname": lastname, "position": position, "gender": gender, "location": location, "profile_link": profile_link})
		else:
			if (firstname != "LinkedIn" and lastname != "Member"):
				employee_dict.append({"firstname": firstname, "lastname": lastname, "position": position, "gender": gender, "location": location, "profile_link": profile_link})
	
	return employee_dict

def progressbar(it, prefix="", size=60, out=sys.stdout): # Python3.3+
	count = len(it)
	def show(j):
		x = int(size * j / count)
		if not args.quiet:
			print("{}[{}{}] {}/{}".format(prefix, "#" * x, "." * (size - x), j, count), end='\r', file=out, flush=True)
	show(0)
	for i, item in enumerate(it):
		yield item
		show(i + 1)
	
	if not args.quiet:
		print("\n", flush=True, file=out)

def main():
	if url.startswith('https://www.linkedin.com/company/'):
		try:
			before_keyword, keyword, after_keyword = url.partition('company/')
			company = after_keyword.split('/')[0]

			if not args.quiet:
				print_logo()

				stop_event = threading.Event()
				loading_thread = threading.Thread(target=show_loading_message, args=(stop_event,))
				loading_thread.start()

			company_id = get_company_id(company)

			api2_response = get_employee_data(company_id, 0)
			paging_total = api2_response["paging"]["total"]
			required_pagings = -(-paging_total // 10)

			if not args.quiet and api2_response:
				stop_event.set()
				loading_thread.join()
				print()
				print()

			if not args.quiet:
				print("[i] Company Name: " + company)
				print("[i] Company X-ID: " + company_id)
				print("[i] LN Employees: " + str(paging_total) + " employees found")
				print("[i] Dumping Date: " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
				if mailformat:
					print("[i] Email Format: " + mailformat)
				print()

			employee_dict = []

			for page in progressbar(range(required_pagings), "Progress: ", 40):
				if args.jitter:
					jitter_dict = [0.5, 1, 0.8, 0.3, 3, 1.5, 5]
					jitter = random.choice(jitter_dict)
					time.sleep(jitter)

				api2_response = get_employee_data(company_id, page * 10)
				for i in range(3):
					try:
						test = api2_response["elements"][i]["items"][0]['itemUnion']['entityResult']['title']['text']
						results = api2_response["elements"][i]["items"]
						employee_dict.extend(parse_employee_results(results))
					except:
						pass

			l = employee_dict
			seen = set()
			new_l = []
			for d in l:
				t = tuple(sorted(d.items()))
				if t not in seen:
					seen.add(t)
					new_l.append(d)
			employee_dict = new_l

			match args.format:
				case 'csv':
					if mailformat:
						legende = "Firstname;Lastname;Email;Position;Gender;Location;Profile"
					else:
						legende = "Firstname;Lastname;Position;Gender;Location;Profile"

					if args.output:
						with open(args.output, 'a') as output_file:
							output_file.write(legende)
							for person in employee_dict:
								if mailformat:
									output_file.write(person["firstname"]+";"+person["lastname"]+";"+mailformat.format(person["firstname"].replace(".","").lower().translate(special_char_map),person["lastname"].replace(".","").lower().translate(special_char_map))+";"+person["position"]+";"+person["gender"]+";"+person["location"]+";"+person["profile_link"])
								else:
									output_file.write(";".join(person.values()))
							print(f'Result save in {args.output}')
							
					else:
						print(legende)
						for person in employee_dict:
							if mailformat:
								print(person["firstname"]+";"+person["lastname"]+";"+mailformat.format(person["firstname"].replace(".","").lower().translate(special_char_map),person["lastname"].replace(".","").lower().translate(special_char_map))+";"+person["position"]+";"+person["gender"]+";"+person["location"]+";"+person["profile_link"])
							else:
								print(";".join(person.values()))
				case 'json':
					json_output = { args.url : employee_dict }

					if args.output:
						with open(args.output, 'a') as output_file:
							json.dump(json_output, output_file, indent=4)
						print(f'Result save in {args.output}')
					else:
						print(json_output)


			if not args.quiet:
				print()
				print("[i] Successfully crawled " + str(len(employee_dict)) + " unique " + str(company) + " employee(s). Hurray ^_-")

		except Exception as e:
			print("[!] Exception. Either API has changed and this script is broken or authentication failed.")
			print("    > Set 'li_at' variable permanently in script or use the '--cookie' CLI flag!")
			print("[debug] " + str(e))
	else:
		print()
		print("[!] Invalid URL provided.")
		print("[i] Example URL: 'https://www.linkedin.com/company/apple'")

if __name__ == "__main__":
	main()
	

README.md is the final checklist for the booking bot, test each feature and see which is missing/bugged

1. Update all listing of bookings to rank by time start ascending then if same, duration ascending

2. Able to be Chairman of Sport and Captain of Dance and still see MPSH logic (If assign properly, isn't an issue)

3. Able to crash the bot if spammed edit and then exit_edit

Traceback (most recent call last):
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/main.py", line 16, in <module>
    bot.polling(none_stop=True)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/telebot/__init__.py", line 1198, in polling
    self.__threaded_polling(non_stop=non_stop, interval=interval, timeout=timeout, long_polling_timeout=long_polling_timeout,
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/telebot/__init__.py", line 1273, in __threaded_polling
    raise e
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/telebot/__init__.py", line 1235, in __threaded_polling
    self.worker_pool.raise_exceptions()
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/telebot/util.py", line 150, in raise_exceptions
    raise self.exception_info
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/telebot/util.py", line 93, in run
    task(*args, **kwargs)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/telebot/__init__.py", line 9233, in _run_middlewares_and_handler
    result = handler['function'](message)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/edit_booking.py", line 145, in exit_edit_command
    send_main_menu(user["user_id"])
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/registration.py", line 79, in send_main_menu
    user = get_user_info(chat_id)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/db_helpers.py", line 21, in get_user_info
    response = supabase.table("users").select("*").eq("user_id", user_id).execute()
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/postgrest/_sync/request_builder.py", line 58, in execute
    r = self.session.request(
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_client.py", line 825, in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_client.py", line 914, in send
    response = self._send_handling_auth(
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_client.py", line 942, in _send_handling_auth
    response = self._send_handling_redirects(
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_client.py", line 979, in _send_handling_redirects
    response = self._send_single_request(request)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_client.py", line 1014, in _send_single_request
    response = transport.handle_request(request)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_transports/default.py", line 250, in handle_request
    resp = self._pool.handle_request(req)
  File "/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/lib/python3.9/contextlib.py", line 135, in __exit__
    self.gen.throw(type, value, traceback)
  File "/Users/winston/Developer/Projects/Facility-Booking-Bot/.venv/lib/python3.9/site-packages/httpx/_transports/default.py", line 118, in map_httpcore_exceptions
    raise mapped_exc(message) from exc
httpx.ReadError: [Errno 35] Resource temporarily unavailable
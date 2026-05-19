# states.py
from vkbottle import BaseStateGroup


class BookingStates(BaseStateGroup):
    WAITING_SERVICE = "waiting_service"
    WAITING_MASTER = "waiting_master"
    WAITING_DATE = "waiting_date"
    WAITING_DATE_PAGE = "waiting_date_page"
    WAITING_TIME = "waiting_time"
    WAITING_TIME_PAGE = "waiting_time_page"
    WAITING_NAME = "waiting_name"
    WAITING_PHONE = "waiting_phone"
    WAITING_CANCEL_CONFIRM = "waiting_cancel_confirm"


class AdminStates(BaseStateGroup):
    WAITING_ADD_MASTER_NAME = "waiting_add_master_name"
    WAITING_ADD_MASTER_SERVICES = "waiting_add_master_services"
    WAITING_ADD_MASTER_VK_ID = "waiting_add_master_vk_id"
    WAITING_SET_MASTER_VK_ID = "waiting_set_master_vk_id"
    WAITING_ADD_SLOTS_CHOOSE_MASTER = "waiting_add_slots_choose_master"
    WAITING_ADD_SLOTS = "waiting_add_slots"
    WAITING_CLOSE_DAY = "waiting_close_day"
    WAITING_CLOSE_DAY_MASTER = "waiting_close_day_master"

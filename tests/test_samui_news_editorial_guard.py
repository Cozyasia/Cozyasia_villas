import unittest

import samui_news_editorial_guard as guard


class EditorialGuardTests(unittest.TestCase):
    def test_rejects_car_and_bike_rental_ad_from_samui_chat(self):
        text = (
            "Аренда авто и байков на Самуи. Свобода передвижения без переплат за такси — "
            "авто от 667 бат/день и байки в отличном состоянии."
        )
        self.assertTrue(guard.is_commercial_offer(text, "Самуи Чат Объявления Барахолка Недвижимость"))
        self.assertFalse(guard.is_editorial_news_text(text, "Самуи Чат Объявления Барахолка Недвижимость"))

    def test_rejects_villa_rental_ad(self):
        text = (
            "Аренда виллы в Чавенг Ной. Предлагается вилла с тремя спальнями, "
            "приватным бассейном и видом на море за 180 000 THB/мес."
        )
        self.assertTrue(guard.is_commercial_offer(text, "Аренда вилл и домов Самуи | Cozy Asia"))
        self.assertFalse(guard.is_editorial_news_text(text, "Аренда вилл и домов Самуи | Cozy Asia"))

    def test_rejects_long_non_news_message_from_geo_chat(self):
        text = (
            "Самуи прекрасный остров. Сегодня делимся большой подборкой полезных советов, "
            "контактов и предложений для приезжающих. Пишите в личные сообщения, расскажем подробнее."
        )
        self.assertFalse(guard.is_editorial_news_text(text, "Samui Community Chat"))

    def test_accepts_earthquake_event(self):
        text = "У Ко Панган зафиксировано землетрясение, сейсмологи уточняют магнитуду и район эпицентра."
        self.assertFalse(guard.is_commercial_offer(text, "Samui News"))
        self.assertTrue(guard.is_editorial_news_text(text, "Samui News"))

    def test_accepts_police_or_transport_incident(self):
        text = "Полиция Самуи перекрыла участок дороги после ДТП; движение временно направляют в объезд."
        self.assertTrue(guard.is_editorial_news_text(text, "Koh Samui Updates"))

    def test_accepts_significant_opening(self):
        text = "На Самуи открылся новый крупный отель на 180 номеров; объект начал принимать гостей сегодня."
        self.assertTrue(guard.is_editorial_news_text(text, "Koh Samui Tourism News"))

    def test_parse_retract_message_ids(self):
        self.assertEqual([34, 35], guard._parse_message_ids("34, 35;bad;0;-2"))


if __name__ == "__main__":
    unittest.main()

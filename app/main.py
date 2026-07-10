from app import db


def show_all_receipts():
    receipts = db.get_all_receipts()
    if not receipts:
        print("Чеков нет в базе.")
        return

    print("\n=== Все чеки ===")
    print("ID | Номер чека | Дата | Магазин | Сумма")
    print("-" * 60)
    for receipt in receipts:
        print(f"{receipt[0]} | {receipt[1]} | {receipt[2]} | {receipt[3]} | {receipt[4]:.2f} EUR")


def show_items_for_receipt():
    try:
        receipt_id = int(input("Введите ID чека: "))
    except ValueError:
        print("Неверный ID.")
        return

    items = db.get_items_by_receipt(receipt_id)
    if not items:
        print("Товары не найдены.")
        return

    print("\n=== Товары по чеку ===")
    print("Название | Кол-во | Цена | Категория")
    print("-" * 60)
    for item in items:
        print(f"{item[0]} | {item[1]} | {item[2]:.2f} | {item[3]}")


def show_total_spent():
    total = db.get_total_spent()
    print(f"\nОбщая сумма расходов: {total:.2f} EUR")


def main():
    db.create_tables()
    while True:
        print("\n=== Receipt Tracker CLI ===")
        print("1. Показать все чеки")
        print("2. Показать товары по чеку")
        print("3. Показать общую сумму расходов")
        print("4. Выход")

        choice = input("Выберите опцию: ")
        if choice == "1":
            show_all_receipts()
        elif choice == "2":
            show_items_for_receipt()
        elif choice == "3":
            show_total_spent()
        elif choice == "4":
            print("До свидания.")
            break
        else:
            print("Неверный выбор, попробуйте снова.")


if __name__ == "__main__":
    main()

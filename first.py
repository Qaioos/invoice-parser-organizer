""" countriesOne = ["Egypt", "KSA", "Kwt"]
countryOneDiscount = 80

countryTow = ["Italy", "Usa"]
countryTowDiscount = 50

myCountry = "Usa"


if myCountry in countriesOne:
    print(f"Your country is {myCountry} and your discount is {countryOneDiscount}%")

else:
    print(f"Your country is {myCountry} and your discount is {countryTowDiscount}%")


 """
""" -- practical Membership Control -- """

admins = ["Ahmed", "Ali", "Mohamed"]

name = input("Enter your name: ").strip().capitalize()

if name in admins:
    print(f"Welcome back, {name}!")
    option = input("Delete or update? your name  ").strip().lower()
    
    if option == "delete":
        admins.remove(name)
        print(f"Your name {name} has been deleted from the list of admins.")
    
    elif option == "update":
        new_name = input("Enter your new name: ").strip().capitalize()
        admins[admins.index(name)] = new_name
        print(f"Your name has been updated to {new_name}.")
        print(f"Your name has been updated to {admins}.")
    
    else:
        print("Invalid option. Please choose 'delete' or 'update'.")
    
else:
    print(f"Your name is not in the list of admins.")
























































































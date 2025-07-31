import os
from dotenv import load_dotenv
from app import create_app


load_dotenv()


config_name = os.getenv('FLASK_CONFIG', 'development')


app = create_app(config_name)


from seed import seed_command
app.cli.add_command(seed_command)

if __name__ == '__main__':
    
    app.run(debug=True)
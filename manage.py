"""Admin setup. Run `python manage.py create-admin` from project root."""
import getpass
import secrets
import sys
from backend.app import init_db,connection,make_hash

if __name__=='__main__':
    if len(sys.argv)!=2 or sys.argv[1]!='create-admin':
        print('Uso: python manage.py create-admin');sys.exit(1)
    init_db()
    username=input('Usuário admin [barbeiro]: ').strip() or 'barbeiro'
    pwd=getpass.getpass('Senha forte (mínimo 12 caracteres): ')
    again=getpass.getpass('Repita a senha: ')
    if len(pwd)<12 or pwd!=again:
        print('Senha inválida ou confirmação diferente');sys.exit(1)
    salt=secrets.token_hex(16)
    with connection() as db:
        db.execute('INSERT INTO admin(id,username,salt,password_hash) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username,salt=excluded.salt,password_hash=excluded.password_hash',(username,salt,make_hash(pwd,salt)))
        db.execute('DELETE FROM sessions')
    print('Administrador configurado. Acesse /admin.')

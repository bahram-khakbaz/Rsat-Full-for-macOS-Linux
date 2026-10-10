import asyncio
import json

import pytest
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.main import validation_error
from app.routers.ad import PasswordBody, UserCreate


def test_reset_accepts_eight_characters_and_preserves_password():
    assert PasswordBody(new_password=' Abcd1! ').new_password == ' Abcd1! '
    with pytest.raises(ValidationError):
        PasswordBody(new_password='Abcd1!x')
    with pytest.raises(ValidationError):
        PasswordBody(new_password='x' * 257)


def test_create_uses_same_eight_character_floor():
    assert UserCreate(sam_account_name='test', given_name='Test', surname='User',
                      display_name='Test User', ou='OU=Test,DC=example,DC=com',
                      password='Abcd12!x').password == 'Abcd12!x'


def test_validation_response_does_not_echo_rejected_credentials():
    secret = 'secret!'
    with pytest.raises(ValidationError) as error:
        PasswordBody(new_password=secret)
    exception = RequestValidationError(error.value.errors(), body={'new_password': secret})
    response = asyncio.run(validation_error(None, exception))
    assert response.status_code == 422
    assert secret.encode() not in response.body
    detail = json.loads(response.body)['detail'][0]
    assert detail['loc'] == ['new_password']
    assert '8 characters' in detail['msg']
    assert 'input' not in detail and 'ctx' not in detail

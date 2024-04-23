#!/bin/bash

url=$1

wget -mkEpnp "$url"
ls "$url"

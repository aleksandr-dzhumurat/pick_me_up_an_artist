# SrtSwipe: an app to explore art and artists
Pick me up an artist: painter recommendations based on swipes

# Exploitation

```shell
make build
```

Start API

```shell
make run
```

Start Streamlit client

```shell
make run-frontend
```

Check browser [0.0.0.0:8080](http://0.0.0.0:8080/)

# Algorithm

Sample random tag

* with $\epsilon$ sample random tag
* with $1 - \epsilon$ choose tag with the highest positive interactions count (from this user)

Sample content with this tag

Save user feedback (positive or negative) with generated tag and use int on the next iteration to sample next tag.


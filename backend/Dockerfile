FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /app ./cmd/server

FROM alpine:3.23
RUN apk add --no-cache ca-certificates
COPY --from=builder /app /app
EXPOSE 8080
CMD ["/app"]

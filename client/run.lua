local event = require("event")

local executor = require("src.executor")
local env = require("env")
local logger = require("lib/logger")

local timerId  -- 存储计时器的 ID
local shouldExit = false  -- 退出标志

local args = {...}
if #args >= 1 then
    if args[1] == "--debug" then
        logger.set_level("DEBUG")
        logger.debug("Debug mode has been enabled.")
    end
end

local function pollServer()
    local success, info = xpcall(function()
        -- 检查是否需要退出
        if shouldExit then
            logger.info("Exiting polling...")
            event.cancel(timerId)  -- 取消定时器
            return
        end

        logger.debug("Polling... Free Memory: ".. require("computer").freeMemory())

        -- 获取命令和 taskId
        local taskId, command_table, isChunked = executor.fetchCommands()
        os.sleep(0)

        if isChunked then
            logger.debug("Using chunked upload")
        end

        if taskId and command_table then
            -- 任务执行期间保持心跳；断电或崩溃后服务端能及时终止任务。
            local heartbeat = executor.startHeartbeat(taskId)
            -- 处理命令并获取结果；内存不足等异常也要向上报，避免任务卡在 PENDING。
            local process_ok, command_result_table = xpcall(function()
                return executor.processCommands(command_table, isChunked)
            end, debug.traceback)
            if not process_ok then
                executor.stopHeartbeat(heartbeat)
                executor.reportClientError(taskId, "客户端执行任务失败：" .. tostring(command_result_table))
                return
            end
            os.sleep(0)

            logger.debug("Reporting results for Task ID: " .. tostring(taskId))
            -- 将执行结果和 taskId 一起报告回服务器
            local chunked_data = command_result_table[1]
            local report_ok, report_err
            if isChunked and type(chunked_data) == "table" and #chunked_data > 0 then
                report_ok, report_err = xpcall(function()
                    executor.reportChunkedResults(taskId, chunked_data)
                end, debug.traceback)
            else
                -- 结果不是可分块的数据（例如内存不足错误），使用普通上报。
                report_ok, report_err = xpcall(function()
                    executor.reportResults(taskId, command_result_table)
                end, debug.traceback)
            end

            executor.stopHeartbeat(heartbeat)
            if not report_ok then
                command_result_table = nil
                chunked_data = nil
                if collectgarbage then
                    pcall(collectgarbage, "collect")
                end
                executor.reportClientError(taskId, "客户端上报失败（可能内存不足）：" .. tostring(report_err))
            end
        else
            logger.debug("No commands received or invalid response.")
        end
    end, debug.traceback)

    -- 处理发生的任何错误
    if not success then
        logger.error(info)
    end
end


-- 启动定时器
timerId = event.timer(env.pollingInterval, pollServer, math.huge)


logger.info("Program started at " .. os.date("%Y-%m-%d %H:%M:%S"))
while true do
    local eventType = event.pull()
    if eventType == "interrupted" then
        shouldExit = true
        if event.cancel(timerId) then
            logger.info("Interrupt received, shutting down...")
        else
            logger.error("error")
        end
        break
    end
end
